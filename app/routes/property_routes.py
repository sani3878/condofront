from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from ..blueprints import property_bp
from ..helpers import query_one, query_all, get_db

def get_setup_status(user):
    """Check what's been set up for this user."""
    status = {
        'has_property': False,
        'has_rooms': False,
        'has_staff': False,
        'property': None,
        'room_count': 0,
        'staff_count': 0,
    }

    if not user.property_id:
        return status

    status['has_property'] = True
    status['property'] = query_one("""
        SELECT * FROM tblproperty WHERE idno = %s
    """, [user.property_id])

    room = query_one("""
        SELECT COUNT(*) as cnt FROM tblroom
        WHERE property_id = %s AND is_active = TRUE
    """, [user.property_id])
    status['room_count']  = room['cnt'] if room else 0
    status['has_rooms']   = status['room_count'] > 0

    staff = query_one("""
        SELECT COUNT(*) as cnt FROM tbluser
        WHERE property_id = %s AND is_active = TRUE
    """, [user.property_id])
    status['staff_count'] = staff['cnt'] if staff else 0
    status['has_staff']   = status['staff_count'] > 0

    return status


@property_bp.route('/dashboard')
@login_required
def dashboard():
    status = get_setup_status(current_user)
    return render_template('property/dashboard.html',
        active_page='settings', status=status)


@property_bp.route('/setup', methods=['GET', 'POST'])
@login_required
def setup():
    existing_property = None
    if current_user.property_id:
        existing_property = query_one("""
            SELECT * FROM tblproperty WHERE idno = %s
        """, [current_user.property_id])

    if request.method == 'POST':
        property_name = request.form.get('property_name', '').strip()
        address       = request.form.get('address', '').strip()
        property_code = request.form.get('property_code', '').strip()

        if not property_name:
            flash('กรุณากรอกชื่อโครงการ', 'danger')
            return redirect(url_for('property.setup'))

        db  = get_db()
        cur = db.cursor()

        try:
            if existing_property:
                # Editing an already-created property
                cur.execute("""
                    UPDATE tblproperty
                    SET property_name = %s,
                        property_code = %s,
                        address = %s
                    WHERE idno = %s
                """, [property_name,
                      property_code or None,
                      address or None,
                      existing_property['idno']])
                db.commit()
                flash('บันทึกข้อมูลโครงการสำเร็จแล้ว!', 'success')
                return redirect(url_for('property.dashboard'))

            # Creating a new property (first time setup)
            cur.execute("""
                INSERT INTO tblproperty
                    (customer_id, property_name, property_code,
                     address, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING idno
            """, [current_user.customer_id,
                  property_name,
                  property_code or None,
                  address or None])
            property_id = cur.fetchone()['idno']

            # Create subscription using the package chosen at registration
            # (falls back to the Free package if none was set)
            customer_pkg = query_one("""
                SELECT package_id FROM tblcustomer WHERE idno = %s
            """, [current_user.customer_id])

            package_id = customer_pkg['package_id'] if customer_pkg else None
            if not package_id:
                free_pkg = query_one("""
                    SELECT idno FROM tblpackage
                    WHERE package_name = 'Free' AND is_active = TRUE
                    LIMIT 1
                """)
                package_id = free_pkg['idno'] if free_pkg else None

            if package_id:
                cur.execute("""
                    INSERT INTO tblsubscription
                        (property_id, package_id, start_date, is_active)
                    VALUES (%s, %s, CURRENT_DATE, TRUE)
                """, [property_id, package_id])

            # Link user to this property
            cur.execute("""
                UPDATE tbluser SET property_id = %s
                WHERE idno = %s
            """, [property_id, current_user.id])

            db.commit()

            # Update current user object
            current_user.property_id = property_id

            flash('สร้างโครงการสำเร็จแล้ว!', 'success')
            return redirect(url_for('property.dashboard'))

        except Exception as e:
            db.rollback()
            flash(f'เกิดข้อผิดพลาด: {str(e)}', 'danger')

    return render_template('property/setup.html', property=existing_property)


@property_bp.route('/rooms')
@login_required
def rooms():
    status = get_setup_status(current_user)
    room_list = query_all("""
        SELECT * FROM tblroom
        WHERE property_id = %s AND is_active = TRUE
        ORDER BY building, room_no
    """, [current_user.property_id]) if current_user.property_id else []

    return render_template('property/rooms.html',
                           status=status,
                           rooms=room_list)


@property_bp.route('/users')
@login_required
def users():
    status = get_setup_status(current_user)
    staff = query_all("""
        SELECT u.*, r.role_name
        FROM tbluser u
        JOIN tblrole r ON u.role_id = r.idno
        WHERE u.property_id = %s AND u.is_active = TRUE
        ORDER BY r.idno, u.fullname
    """, [current_user.property_id]) if current_user.property_id else []

    # Subscription limit info
    max_user = None
    package_name = None
    if current_user.property_id:
        sub = query_one("""
            SELECT pkg.max_user, pkg.package_name
            FROM tblsubscription s
            JOIN tblpackage pkg ON s.package_id = pkg.idno
            WHERE s.property_id = %s AND s.is_active = TRUE
            ORDER BY s.idno DESC LIMIT 1
        """, [current_user.property_id])
        if sub:
            max_user = sub['max_user']
            package_name = sub['package_name']

    roles = query_all("SELECT * FROM tblrole ORDER BY idno")

    return render_template('property/users.html',
        active_page='staff',
        status=status,
        staff=staff,
        roles=roles,
        staff_count=len(staff),
        max_user=max_user,
        package_name=package_name)


@property_bp.route('/billing')
@login_required
def billing():
    status = get_setup_status(current_user)

    current_sub = None
    if current_user.property_id:
        current_sub = query_one("""
            SELECT s.idno AS sub_id, s.start_date, s.expire_date,
                   pkg.idno AS package_id, pkg.package_name, pkg.monthly_fee,
                   pkg.max_room, pkg.max_user, pkg.max_parcel
            FROM tblsubscription s
            JOIN tblpackage pkg ON s.package_id = pkg.idno
            WHERE s.property_id = %s AND s.is_active = TRUE
            ORDER BY s.idno DESC LIMIT 1
        """, [current_user.property_id])

    # Current usage against the plan's limits
    usage = {'room': 0, 'user': 0, 'parcel': 0}
    if current_user.property_id:
        usage['room'] = query_one("""
            SELECT COUNT(*) AS cnt FROM tblroom
            WHERE property_id = %s AND is_active = TRUE
        """, [current_user.property_id])['cnt']

        usage['user'] = query_one("""
            SELECT COUNT(*) AS cnt FROM tbluser
            WHERE property_id = %s AND is_active = TRUE
        """, [current_user.property_id])['cnt']

        usage['parcel'] = query_one("""
            SELECT COUNT(*) AS cnt FROM tblparcel
            WHERE property_id = %s AND deleted_at IS NULL
        """, [current_user.property_id])['cnt']

    all_packages = query_all("""
        SELECT * FROM tblpackage
        WHERE is_active = TRUE
        ORDER BY monthly_fee
    """)

    return render_template('property/billing.html',
        active_page='settings',
        status=status,
        current_sub=current_sub,
        usage=usage,
        all_packages=all_packages)


@property_bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    from werkzeug.security import generate_password_hash
    import secrets

    if not current_user.property_id:
        flash('กรุณาตั้งค่าโครงการก่อน', 'danger')
        return redirect(url_for('property.dashboard'))

    # ── Enforce package user limit ──────────────────────────
    sub = query_one("""
        SELECT pkg.max_user
        FROM tblsubscription s
        JOIN tblpackage pkg ON s.package_id = pkg.idno
        WHERE s.property_id = %s AND s.is_active = TRUE
        ORDER BY s.idno DESC LIMIT 1
    """, [current_user.property_id])

    current_count = query_one("""
        SELECT COUNT(*) as cnt FROM tbluser
        WHERE property_id = %s AND is_active = TRUE
    """, [current_user.property_id])['cnt']

    if sub and sub['max_user'] and current_count >= sub['max_user']:
        flash(f'แพ็กเกจของคุณรองรับผู้ใช้งานสูงสุด {sub["max_user"]} คน '
              f'กรุณาอัปเกรดแพ็กเกจเพื่อเพิ่มผู้ใช้งาน', 'danger')
        return redirect(url_for('property.users'))

    fullname = request.form.get('fullname', '').strip()
    email    = request.form.get('email', '').strip().lower()
    mobile   = request.form.get('mobile', '').strip()
    role_id  = request.form.get('role_id')

    if not all([fullname, email, role_id]):
        flash('กรุณากรอกข้อมูลให้ครบ', 'danger')
        return redirect(url_for('property.users'))

    if query_one('SELECT idno FROM tbluser WHERE email = %s', [email]):
        flash('อีเมลนี้ถูกใช้งานแล้ว', 'danger')
        return redirect(url_for('property.users'))

    # Temporary password — staff resets via "forgot password" on first login
    temp_password = secrets.token_urlsafe(8)

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO tbluser
            (customer_id, property_id, role_id,
             email, password_hash, fullname, mobile, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
    """, [current_user.customer_id, current_user.property_id, role_id,
          email, generate_password_hash(temp_password), fullname, mobile or None])
    db.commit()

    flash(f'เพิ่มพนักงานสำเร็จ! รหัสผ่านชั่วคราว: {temp_password} '
          f'(กรุณาแจ้งพนักงานให้เปลี่ยนรหัสผ่านทันที)', 'success')
    return redirect(url_for('property.users'))


@property_bp.route('/users/deactivate/<int:user_id>', methods=['POST'])
@login_required
def deactivate_user(user_id):
    if user_id == current_user.id:
        flash('ไม่สามารถปิดใช้งานบัญชีตัวเองได้', 'danger')
        return redirect(url_for('property.users'))

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tbluser SET is_active = FALSE
        WHERE idno = %s AND property_id = %s
    """, [user_id, current_user.property_id])
    db.commit()

    flash('ปิดใช้งานพนักงานสำเร็จ', 'success')
    return redirect(url_for('property.users'))


@property_bp.route('/rooms/add', methods=['POST'])
@login_required
def add_room():
    building = request.form.get('building', '').strip().upper()
    room_no  = request.form.get('room_no', '').strip()
    floor    = request.form.get('floor', '').strip()

    if not room_no:
        flash('กรุณากรอกหมายเลขห้อง', 'danger')
        return redirect(url_for('property.rooms'))

    # Check duplicate
    existing = query_one("""
        SELECT idno FROM tblroom
        WHERE property_id = %s
          AND room_no = %s
          AND (building = %s OR (building IS NULL AND %s = ''))
          AND is_active = TRUE
    """, [current_user.property_id, room_no,
          building or None, building])

    if existing:
        flash(f'ห้อง {building}{room_no} มีอยู่แล้วในระบบ', 'danger')
        return redirect(url_for('property.rooms'))

    try:
        import secrets as _sec
        invite_code = _sec.token_urlsafe(6).upper()[:8]

        db  = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO tblroom
                (property_id, building, room_no, floor, invite_code, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE)
        """, [current_user.property_id,
              building or None,
              room_no,
              int(floor) if floor else None,
              invite_code])
        db.commit()
        flash(f'เพิ่มห้อง {building}{room_no} สำเร็จแล้ว! รหัสเชิญ: {invite_code}', 'success')

    except Exception as e:
        db.rollback()
        flash(f'เกิดข้อผิดพลาด: {str(e)}', 'danger')

    return redirect(url_for('property.rooms'))


@property_bp.route('/rooms/download-template')
@login_required
def download_template():
    import io
    import openpyxl
    from flask import send_file

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Rooms'

    # Headers
    ws['A1'] = 'building'
    ws['B1'] = 'room_no'
    ws['C1'] = 'floor'

    # Instructions row
    ws['A2'] = 'A'
    ws['B2'] = '101'
    ws['C2'] = '1'
    ws['A3'] = 'A'
    ws['B3'] = '102'
    ws['C3'] = '1'
    ws['A4'] = 'B'
    ws['B4'] = '101'
    ws['C4'] = '1'
    ws['A5'] = 'ก'
    ws['B5'] = '201'
    ws['C5'] = '2'

    # Style headers
    from openpyxl.styles import Font, PatternFill
    for cell in ['A1', 'B1', 'C1']:
        ws[cell].font = Font(bold=True, color='FFFFFF')
        ws[cell].fill = PatternFill('solid', fgColor='1E3A5F')

    # Column widths
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 15

    # Save to buffer
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='condofront_rooms_template.xlsx'
    )


@property_bp.route('/rooms/import', methods=['POST'])
@login_required
def import_rooms():
    import openpyxl

    file = request.files.get('file')
    if not file or file.filename == '':
        flash('กรุณาเลือกไฟล์ Excel', 'danger')
        return redirect(url_for('property.rooms'))

    try:
        wb      = openpyxl.load_workbook(file)
        ws      = wb.active
        rows    = list(ws.iter_rows(min_row=2, values_only=True))

        success = 0
        skipped = 0
        errors  = 0

        db  = get_db()
        cur = db.cursor()

        for row in rows:
            building = str(row[0]).strip().upper() if row[0] else ''
            room_no  = str(row[1]).strip()         if row[1] else ''
            floor    = row[2]

            if not room_no:
                skipped += 1
                continue

            # Check duplicate
            cur.execute("""
                SELECT idno FROM tblroom
                WHERE property_id = %s
                  AND room_no = %s
                  AND is_active = TRUE
            """, [current_user.property_id, room_no])

            if cur.fetchone():
                skipped += 1
                continue

            try:
                import secrets as _sec
                invite_code = _sec.token_urlsafe(6).upper()[:8]

                cur.execute("""
                    INSERT INTO tblroom
                        (property_id, building, room_no, floor, invite_code, is_active)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                """, [current_user.property_id,
                      building or None,
                      room_no,
                      int(floor) if floor else None,
                      invite_code])
                success += 1
            except Exception:
                errors += 1

        db.commit()

        msg = f'นำเข้าสำเร็จ {success} ห้อง'
        if skipped: msg += f' · ข้ามไป {skipped} ห้อง (ซ้ำหรือว่าง)'
        if errors:  msg += f' · ผิดพลาด {errors} ห้อง'

        flash(msg, 'success' if success > 0 else 'warning')

    except Exception as e:
        flash(f'ไม่สามารถอ่านไฟล์ได้: {str(e)}', 'danger')

    return redirect(url_for('property.rooms'))
