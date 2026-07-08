import secrets
from datetime import date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..blueprints import visitor_bp
from ..helpers import query_one, query_all, get_db


def generate_visitor_code():
    """Generate a unique visitor code like VST-A4F8."""
    while True:
        code = 'VST-' + secrets.token_urlsafe(3).upper()[:4]
        existing = query_one(
            "SELECT idno FROM tblvisitor WHERE visitor_code = %s", [code])
        if not existing:
            return code


# ── STAFF ROUTES ────────────────────────────────────────────

@visitor_bp.route('/')
@login_required
def log():
    today  = request.args.get('date', date.today().isoformat())
    search = request.args.get('q', '').strip()
    show   = request.args.get('show', 'default')  # default | today | pending | all

    sql = """
        SELECT v.idno, v.visitor_name, v.id_card, v.purpose,
               v.visitor_code, v.visit_date, v.status,
               v.time_in, v.time_out, v.note,
               r.room_no, r.building,
               u.fullname AS logged_by_name,
               ru.fullname AS registered_by_name
        FROM tblvisitor v
        LEFT JOIN tblroom r  ON v.room_id = r.idno
        LEFT JOIN tbluser u  ON v.logged_by = u.idno
        LEFT JOIN tbluser ru ON v.registered_by = ru.idno
        WHERE v.property_id = %s
    """
    params = [current_user.property_id]

    if search:
        sql += """
            AND (v.visitor_name ILIKE %s
              OR v.visitor_code ILIKE %s
              OR r.room_no ILIKE %s)
        """
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    elif show == 'today':
        sql += " AND (v.visit_date = %s OR v.time_in::date = %s)"
        params += [today, today]
    elif show == 'pending':
        sql += " AND v.status = 'pending'"
    elif show == 'all':
        pass  # no filter
    else:
        # Default — today's visits + all pending pre-registered (future dates too)
        sql += """
            AND (
                v.visit_date = %s
                OR v.time_in::date = %s
                OR v.status = 'pending'
            )
        """
        params += [today, today]

    sql += " ORDER BY v.status ASC, v.visit_date ASC, v.idno DESC LIMIT 100"

    visitors = query_all(sql, params)
    rooms = query_all("""
        SELECT idno, building, room_no FROM tblroom
        WHERE property_id = %s AND is_active = TRUE
        ORDER BY building, room_no
    """, [current_user.property_id])

    currently_in = [v for v in visitors if v['status'] == 'arrived']
    pending      = [v for v in visitors if v['status'] == 'pending']

    return render_template('visitor/log.html',
        active_page='visitor',
        visitors=visitors,
        rooms=rooms,
        currently_in=currently_in,
        pending=pending,
        today=today,
        search=search,
        show=show)


@visitor_bp.route('/checkin', methods=['POST'])
@login_required
def checkin():
    """Staff manually checks in a walk-in visitor."""
    visitor_name = request.form.get('visitor_name', '').strip()
    room_id      = request.form.get('room_id') or None
    id_card      = request.form.get('id_card', '').strip() or None
    purpose      = request.form.get('purpose', '').strip() or None

    if not visitor_name:
        flash('กรุณากรอกชื่อผู้มาติดต่อ', 'danger')
        return redirect(url_for('visitor.log'))

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO tblvisitor
            (property_id, room_id, visitor_name, id_card,
             purpose, visitor_code, logged_by, time_in,
             visit_date, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), CURRENT_DATE, 'arrived')
    """, [current_user.property_id, room_id,
          visitor_name, id_card, purpose,
          generate_visitor_code(), current_user.id])
    db.commit()

    flash(f'✅ {visitor_name} — บันทึกเข้าสำเร็จ', 'success')
    return redirect(url_for('visitor.log'))


@visitor_bp.route('/confirm/<code>', methods=['POST'])
@login_required
def confirm_arrival(code):
    """Staff confirms arrival of a pre-registered visitor by QR/code."""
    visitor = query_one("""
        SELECT v.*, r.room_no, r.building
        FROM tblvisitor v
        LEFT JOIN tblroom r ON v.room_id = r.idno
        WHERE v.visitor_code = %s AND v.property_id = %s
    """, [code.upper(), current_user.property_id])

    if not visitor:
        flash(f'ไม่พบรหัส {code}', 'danger')
        return redirect(url_for('visitor.log'))

    if visitor['status'] == 'arrived':
        flash(f'{visitor["visitor_name"]} เช็คอินแล้ว', 'warning')
        return redirect(url_for('visitor.log'))

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblvisitor
        SET status = 'arrived', time_in = NOW(), logged_by = %s
        WHERE visitor_code = %s
    """, [current_user.id, code.upper()])
    db.commit()

    room = f'{visitor["building"] or ""}{visitor["room_no"]}' if visitor['room_no'] else ''
    flash(f'✅ {visitor["visitor_name"]} {room} — เช็คอินสำเร็จ!', 'success')
    return redirect(url_for('visitor.log'))


@visitor_bp.route('/checkout/<int:visitor_id>', methods=['POST'])
@login_required
def checkout(visitor_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblvisitor
        SET time_out = NOW(), status = 'completed'
        WHERE idno = %s AND property_id = %s
    """, [visitor_id, current_user.property_id])
    db.commit()
    flash('บันทึกออกสำเร็จ', 'success')
    return redirect(url_for('visitor.log'))


# ── RESIDENT ROUTES ─────────────────────────────────────────

@visitor_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register_visitor():
    """Resident pre-registers a visitor."""
    if not current_user.is_resident:
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        visitor_name = request.form.get('visitor_name', '').strip()
        visit_date   = request.form.get('visit_date', '').strip()
        purpose      = request.form.get('purpose', '').strip() or None
        id_card      = request.form.get('id_card', '').strip() or None

        if not visitor_name or not visit_date:
            flash('กรุณากรอกชื่อและวันที่', 'danger')
            return redirect(url_for('visitor.register_visitor'))

        code = generate_visitor_code()
        db   = get_db()
        cur  = db.cursor()
        cur.execute("""
            INSERT INTO tblvisitor
                (property_id, room_id, registered_by,
                 visitor_name, id_card, purpose,
                 visitor_code, visit_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            RETURNING idno
        """, [current_user.property_id,
              current_user.unit_id,
              current_user.id,
              visitor_name, id_card, purpose,
              code, visit_date])
        visitor_id = cur.fetchone()['idno']
        db.commit()

        flash(f'ลงทะเบียนผู้มาเยี่ยม {visitor_name} สำเร็จ! รหัส: {code}', 'success')
        return redirect(url_for('visitor.visitor_qr', visitor_id=visitor_id))

    return render_template('visitor/register.html')


@visitor_bp.route('/qr/<int:visitor_id>')
@login_required
def visitor_qr(visitor_id):
    """Show QR code for a pre-registered visitor."""
    visitor = query_one("""
        SELECT v.*, r.room_no, r.building, p.property_name
        FROM tblvisitor v
        LEFT JOIN tblroom r ON v.room_id = r.idno
        LEFT JOIN tblproperty p ON v.property_id = p.idno
        WHERE v.idno = %s AND v.registered_by = %s
    """, [visitor_id, current_user.id])

    if not visitor:
        flash('ไม่พบข้อมูล', 'danger')
        return redirect(url_for('visitor.my_visitors'))

    return render_template('visitor/qr.html', visitor=visitor)


@visitor_bp.route('/my')
@login_required
def my_visitors():
    """Resident sees their pre-registered visitors."""
    if not current_user.is_resident:
        return redirect(url_for('main.home'))

    visitors = query_all("""
        SELECT v.*, r.room_no, r.building
        FROM tblvisitor v
        LEFT JOIN tblroom r ON v.room_id = r.idno
        WHERE v.registered_by = %s
        ORDER BY v.visit_date DESC, v.idno DESC
        LIMIT 20
    """, [current_user.id])

    return render_template('visitor/my_visitors.html', visitors=visitors)
