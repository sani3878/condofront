from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from ..blueprints import auth_bp
from ..models import User
from ..helpers import query_one, query_all, get_db
from ..mail import send_verification_email


# ── HELPER — must be defined before login route ──────────────
def get_next_page(user):
    """Smart redirect based on role and database state."""

    # SuperAdmin goes to admin dashboard
    if user.is_superadmin:
        return url_for('admin.dashboard')

    # Residents go to their own home
    if user.is_resident:
        return url_for('resident.home')

    # Staff — check property setup
    if not user.property_id:
        return url_for('property.dashboard')

    # Check rooms exist
    room_count = query_one("""
        SELECT COUNT(*) as cnt
        FROM tblroom
        WHERE property_id = %s
        AND is_active = TRUE
    """, [user.property_id])

    if not room_count or room_count['cnt'] == 0:
        return url_for('property.dashboard')

    return url_for('main.home')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(get_next_page(current_user))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.get_by_email(email)

        if user and check_password_hash(user.password_hash, password):
            if not user.email_verified:
                flash('กรุณายืนยันอีเมลของคุณก่อนเข้าสู่ระบบ ตรวจสอบกล่องจดหมายของคุณ', 'danger')
                return render_template('auth/login.html', unverified_email=email)

            # Check approval for juristic accounts (not residents, not superadmin)
            if user.is_staff and user.customer_id:
                customer = query_one("""
                    SELECT is_approved FROM tblcustomer WHERE idno = %s
                """, [user.customer_id])
                if customer and not customer['is_approved']:
                    flash('บัญชีของคุณอยู่ระหว่างรอการอนุมัติจากทีมงาน CondoFront '
                          'กรุณารอการติดต่อกลับภายใน 24 ชั่วโมง', 'warning')
                    return render_template('auth/login.html')

            login_user(user, remember='remember' in request.form)
            next_page = request.args.get('next')
            return redirect(next_page or get_next_page(user))

        flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        property_name = request.form.get('property_name', '').strip()
        email         = request.form.get('email', '').strip().lower()
        password      = request.form.get('password', '')
        confirm       = request.form.get('confirm_password', '')
        fullname      = request.form.get('fullname', '').strip()
        mobile        = request.form.get('mobile', '').strip()
        package_id    = request.form.get('package_id')

        # ── Validation ──────────────────────────────────────────
        if not all([customer_name, property_name, email, password, fullname, package_id]):
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('auth.register'))

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.register'))

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('auth.register'))

        if query_one('SELECT idno FROM tbluser WHERE email = %s', [email]):
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))

        # ── Create all records in one transaction ───────────────
        db  = get_db()
        cur = db.cursor()

        import secrets

        try:
            # 1. Create customer (billing entity) — pending approval
            cur.execute("""
                INSERT INTO tblcustomer
                    (customer_name, email, mobile, package_id, is_active, is_approved)
                VALUES (%s, %s, %s, %s, TRUE, FALSE)
                RETURNING idno
            """, [customer_name, email, mobile or None, package_id])
            customer_id = cur.fetchone()['idno']

            # 2. Create property automatically
            cur.execute("""
                INSERT INTO tblproperty
                    (customer_id, property_name, is_active)
                VALUES (%s, %s, TRUE)
                RETURNING idno
            """, [customer_id, property_name])
            property_id = cur.fetchone()['idno']

            # 3. Create subscription using chosen package
            cur.execute("""
                INSERT INTO tblsubscription
                    (property_id, package_id, start_date, is_active)
                VALUES (%s, %s, CURRENT_DATE, TRUE)
            """, [property_id, package_id])

            # 4. Create user linked to customer AND property
            verify_token = secrets.token_urlsafe(32)

            cur.execute("""
                INSERT INTO tbluser
                    (customer_id, property_id, role_id,
                     email, password_hash, fullname, mobile, is_active,
                     email_verified, verify_token, verify_sent_at)
                VALUES (%s, %s, 2, %s, %s, %s, %s, TRUE,
                        FALSE, %s, NOW())
            """, [customer_id, property_id, email,
                  generate_password_hash(password),
                  fullname, mobile or None,
                  verify_token])

            db.commit()

            # 5. Send verification email to user
            verify_url = url_for('auth.verify_email', token=verify_token, _external=True)
            success, error = send_verification_email(email, fullname, verify_url)
            if not success:
                print(f"EMAIL ERROR: {error}", flush=True)

            # 6. Notify admin of new pending registration
            from ..mail import send_contact_email
            send_contact_email(
                name=fullname,
                email=email,
                mobile=mobile or '-',
                message=f'มีการสมัครใหม่รอการอนุมัติ\n\nบริษัท: {customer_name}\nโครงการ: {property_name}\nแพ็กเกจ: {package_id}\n\nกรุณาเข้าสู่ระบบ Admin เพื่ออนุมัติ',
                customer_name=customer_name,
                property_name=property_name
            )

            flash('สมัครสมาชิกสำเร็จ! กรุณายืนยันอีเมลของคุณ '
                  'และรอการอนุมัติจากทีมงาน CondoFront ภายใน 24 ชั่วโมง', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
            return redirect(url_for('auth.register'))

    packages = query_all("""
        SELECT idno, package_name, monthly_fee,
               max_room, max_user, max_parcel
        FROM tblpackage
        WHERE is_active = TRUE
        ORDER BY monthly_fee
    """)
    return render_template('auth/register.html', packages=packages)


@auth_bp.route('/verify/<token>')
def verify_email(token):
    user = query_one("""
        SELECT idno, fullname, verify_sent_at, email_verified
        FROM tbluser
        WHERE verify_token = %s
    """, [token])

    if not user:
        flash('ลิงก์ยืนยันไม่ถูกต้อง หรือถูกใช้งานไปแล้ว', 'danger')
        return redirect(url_for('auth.login'))

    if user['email_verified']:
        flash('อีเมลนี้ได้รับการยืนยันแล้ว กรุณาเข้าสู่ระบบ', 'info')
        return redirect(url_for('auth.login'))

    # Expire after 24 hours
    from datetime import datetime, timedelta
    if user['verify_sent_at'] and datetime.now() - user['verify_sent_at'] > timedelta(hours=24):
        flash('ลิงก์ยืนยันหมดอายุแล้ว กรุณาขอลิงก์ใหม่', 'danger')
        return redirect(url_for('auth.login'))

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tbluser
        SET email_verified = TRUE, verify_token = NULL
        WHERE idno = %s
    """, [user['idno']])
    db.commit()

    flash('ยืนยันอีเมลสำเร็จ! กรุณาเข้าสู่ระบบ', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verification')
def resend_verification():
    import secrets
    email = request.args.get('email', '').strip().lower()

    user = query_one("""
        SELECT idno, fullname, email_verified
        FROM tbluser WHERE email = %s
    """, [email])

    if not user:
        flash('ไม่พบบัญชีนี้ในระบบ', 'danger')
        return redirect(url_for('auth.login'))

    if user['email_verified']:
        flash('อีเมลนี้ได้รับการยืนยันแล้ว กรุณาเข้าสู่ระบบ', 'info')
        return redirect(url_for('auth.login'))

    new_token = secrets.token_urlsafe(32)
    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tbluser
        SET verify_token = %s, verify_sent_at = NOW()
        WHERE idno = %s
    """, [new_token, user['idno']])
    db.commit()

    verify_url = url_for('auth.verify_email', token=new_token, _external=True)
    success, error = send_verification_email(email, user['fullname'], verify_url)

    if success:
        flash('ส่งอีเมลยืนยันใหม่แล้ว กรุณาตรวจสอบกล่องจดหมายของคุณ', 'success')
    else:
        flash('ไม่สามารถส่งอีเมลได้ในขณะนี้ กรุณาลองใหม่ภายหลัง', 'danger')

    return redirect(url_for('auth.login'))


@auth_bp.route('/register/resident', methods=['GET', 'POST'])
def register_resident():
    """Resident self-registration using invite code from staff."""
    import secrets as _secrets

    if request.method == 'POST':
        invite_code  = request.form.get('invite_code', '').strip().upper()
        fullname     = request.form.get('fullname', '').strip()
        email        = request.form.get('email', '').strip().lower()
        mobile       = request.form.get('mobile', '').strip()
        password     = request.form.get('password', '')
        confirm      = request.form.get('confirm_password', '')

        # Validate fields
        if not all([invite_code, fullname, email, password]):
            flash('กรุณากรอกข้อมูลให้ครบ', 'danger')
            return redirect(url_for('auth.register_resident'))

        if password != confirm:
            flash('รหัสผ่านไม่ตรงกัน', 'danger')
            return redirect(url_for('auth.register_resident'))

        if len(password) < 8:
            flash('รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร', 'danger')
            return redirect(url_for('auth.register_resident'))

        # Find room by invite code
        room = query_one("""
            SELECT r.*, p.idno AS property_id, p.property_name
            FROM tblroom r
            JOIN tblproperty p ON r.property_id = p.idno
            WHERE r.invite_code = %s AND r.is_active = TRUE
        """, [invite_code])

        if not room:
            flash('รหัสเชิญไม่ถูกต้อง กรุณาตรวจสอบอีกครั้ง', 'danger')
            return redirect(url_for('auth.register_resident'))

        if query_one('SELECT idno FROM tbluser WHERE email = %s', [email]):
            flash('อีเมลนี้ถูกใช้งานแล้ว', 'danger')
            return redirect(url_for('auth.register_resident'))

        db  = get_db()
        cur = db.cursor()

        try:
            verify_token = _secrets.token_urlsafe(32)

            cur.execute("""
                INSERT INTO tbluser
                    (customer_id, property_id, unit_id, role_id,
                     email, password_hash, fullname, mobile, is_active,
                     email_verified, verify_token, verify_sent_at)
                VALUES (NULL, %s, %s, 4, %s, %s, %s, %s, TRUE,
                        FALSE, %s, NOW())
            """, [room['property_id'], room['idno'],
                  email, generate_password_hash(password),
                  fullname, mobile or None, verify_token])

            db.commit()

            # Send verification email
            verify_url = url_for('auth.verify_email',
                                 token=verify_token, _external=True)
            success, error = send_verification_email(email, fullname, verify_url)
            if not success:
                print(f"EMAIL ERROR: {error}", flush=True)

            flash(f'สมัครสมาชิกสำเร็จ! ห้อง {room["building"] or ""}{room["room_no"]} — {room["property_name"]} '
                  f'กรุณายืนยันอีเมลก่อนเข้าสู่ระบบ', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.rollback()
            flash(f'เกิดข้อผิดพลาด: {str(e)}', 'danger')
            return redirect(url_for('auth.register_resident'))

    # Pre-fill invite code from URL if provided
    invite_code = request.args.get('code', '')
    return render_template('auth/register_resident.html',
                           invite_code=invite_code)



@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    from ..mail import send_reset_email
    import secrets

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash('กรุณากรอกอีเมล', 'danger')
            return redirect(url_for('auth.forgot_password'))

        user = query_one("""
            SELECT idno, fullname, email FROM tbluser
            WHERE email = %s AND is_active = TRUE
        """, [email])

        # Always show success — don't reveal if email exists
        if user:
            reset_token = secrets.token_urlsafe(32)
            db  = get_db()
            cur = db.cursor()
            cur.execute("""
                UPDATE tbluser
                SET reset_token = %s, reset_sent_at = NOW()
                WHERE idno = %s
            """, [reset_token, user['idno']])
            db.commit()

            reset_url = url_for('auth.reset_password',
                                token=reset_token, _external=True)
            success, error = send_reset_email(email, user['fullname'], reset_url)
            if not success:
                print(f"RESET EMAIL ERROR: {error}", flush=True)

        flash('หากอีเมลนี้มีในระบบ เราจะส่งลิงก์รีเซ็ตรหัสผ่านให้ทันที', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    from datetime import datetime, timedelta

    user = query_one("""
        SELECT idno, fullname, reset_sent_at
        FROM tbluser
        WHERE reset_token = %s AND is_active = TRUE
    """, [token])

    if not user:
        flash('ลิงก์รีเซ็ตไม่ถูกต้อง หรือถูกใช้งานไปแล้ว', 'danger')
        return redirect(url_for('auth.login'))

    # Expire after 1 hour
    if user['reset_sent_at'] and \
       datetime.now() - user['reset_sent_at'] > timedelta(hours=1):
        flash('ลิงก์รีเซ็ตหมดอายุแล้ว กรุณาขอลิงก์ใหม่', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if len(password) < 8:
            flash('รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร', 'danger')
            return redirect(request.url)

        if password != confirm:
            flash('รหัสผ่านไม่ตรงกัน', 'danger')
            return redirect(request.url)

        db  = get_db()
        cur = db.cursor()
        cur.execute("""
            UPDATE tbluser
            SET password_hash = %s,
                reset_token   = NULL,
                reset_sent_at = NULL
            WHERE idno = %s
        """, [generate_password_hash(password), user['idno']])
        db.commit()

        flash('เปลี่ยนรหัสผ่านสำเร็จ! กรุณาเข้าสู่ระบบ', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html',
                           token=token,
                           fullname=user['fullname'])


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))





@auth_bp.route('/language/<lang>')
def set_language(lang):
    from flask import session
    if lang in ('th', 'en'):
        session['lang'] = lang
        session.modified = True
    return redirect(request.referrer or url_for('main.home'))


@auth_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    from ..mail import send_contact_email

    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        email   = request.form.get('email', '').strip()
        mobile  = request.form.get('mobile', '').strip()
        message = request.form.get('message', '').strip()

        if not all([name, email, message]):
            flash('กรุณากรอกชื่อ อีเมล และข้อความ', 'danger')
            return redirect(url_for('auth.contact'))

        customer_name = None
        property_name = None
        if current_user.is_authenticated:
            if not name:
                name = current_user.fullname
            customer_name = current_user.fullname
            if current_user.property_id:
                prop = query_one("""
                    SELECT property_name FROM tblproperty WHERE idno = %s
                """, [current_user.property_id])
                property_name = prop['property_name'] if prop else None

        success, error = send_contact_email(
            name, email, mobile, message,
            customer_name=customer_name,
            property_name=property_name
        )

        if success:
            flash('ส่งข้อความสำเร็จ! ทีมงานจะติดต่อกลับโดยเร็วที่สุด', 'success')
            return redirect(url_for('auth.contact'))
        else:
            flash(f'ไม่สามารถส่งข้อความได้ในขณะนี้ กรุณาลองใหม่ภายหลัง', 'danger')
            return redirect(url_for('auth.contact'))

    prefill_name  = current_user.fullname if current_user.is_authenticated else ''
    prefill_email = current_user.email if current_user.is_authenticated else ''
    prefill_mobile = current_user.mobile if current_user.is_authenticated else ''

    return render_template('auth/contact.html',
        active_page='contact',
        prefill_name=prefill_name,
        prefill_email=prefill_email,
        prefill_mobile=prefill_mobile)
