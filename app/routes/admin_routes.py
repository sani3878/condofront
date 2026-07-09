from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from ..blueprints import admin_bp
from ..helpers import query_all, query_one, get_db
from ..mail import _send


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_superadmin:
            flash('ไม่มีสิทธิ์เข้าถึงหน้านี้', 'danger')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    # Platform stats
    stats = query_one("""
        SELECT
            (SELECT COUNT(*) FROM tblcustomer WHERE is_approved = TRUE)  AS total_customers,
            (SELECT COUNT(*) FROM tblcustomer WHERE is_approved = FALSE) AS pending_count,
            (SELECT COUNT(*) FROM tblproperty)                           AS total_properties,
            (SELECT COUNT(*) FROM tbluser WHERE role_id = 4)             AS total_residents,
            (SELECT COUNT(*) FROM tblparcel WHERE deleted_at IS NULL)    AS total_parcels,
            (SELECT COUNT(*) FROM tblparcel WHERE status_id = 0
             AND deleted_at IS NULL)                                      AS waiting_parcels,
            (SELECT COUNT(*) FROM tblfacility_booking
             WHERE status = 'confirmed')                                  AS total_bookings,
            (SELECT COUNT(*) FROM tblservice_request)                    AS total_services
    """)

    # Monthly revenue estimate
    revenue = query_one("""
        SELECT COALESCE(SUM(pkg.monthly_fee), 0) AS mrr
        FROM tblcustomer c
        JOIN tblpackage pkg ON c.package_id = pkg.idno
        WHERE c.is_approved = TRUE
    """)

    # Pending approvals
    pending = query_all("""
        SELECT c.idno, c.customer_name, c.email, c.mobile,
               u.created_at,
               pkg.package_name,
               p.property_name,
               u.fullname,
               (SELECT COUNT(*) FROM tblroom r
                WHERE r.property_id = p.idno) AS room_count
        FROM tblcustomer c
        LEFT JOIN tblpackage  pkg ON c.package_id  = pkg.idno
        LEFT JOIN tblproperty p   ON p.customer_id = c.idno
        LEFT JOIN tbluser     u   ON u.customer_id = c.idno AND u.role_id IN (1,2)
        WHERE c.is_approved = FALSE
        ORDER BY c.idno DESC
    """)

    # All approved customers
    search = request.args.get('q', '').strip()
    sql = """
        SELECT c.idno, c.customer_name, c.email, c.is_active,
               u.created_at,
               pkg.package_name, pkg.monthly_fee,
               p.property_name, p.idno AS property_id,
               u.fullname,
               (SELECT COUNT(*) FROM tblroom r
                WHERE r.property_id = p.idno) AS room_count,
               (SELECT COUNT(*) FROM tbluser usr
                WHERE usr.property_id = p.idno
                AND usr.is_active = TRUE) AS user_count,
               (SELECT COUNT(*) FROM tblparcel par
                WHERE par.property_id = p.idno
                AND par.deleted_at IS NULL) AS parcel_count
        FROM tblcustomer c
        LEFT JOIN tblpackage  pkg ON c.package_id  = pkg.idno
        LEFT JOIN tblproperty p   ON p.customer_id = c.idno
        LEFT JOIN tbluser     u   ON u.customer_id = c.idno AND u.role_id IN (1,2)
        WHERE c.is_approved = TRUE
    """
    params = []
    if search:
        sql += " AND (c.customer_name ILIKE %s OR c.email ILIKE %s OR p.property_name ILIKE %s)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    sql += " ORDER BY c.idno DESC LIMIT 50"
    customers = query_all(sql, params)

    packages = query_all("SELECT * FROM tblpackage WHERE is_active = TRUE ORDER BY monthly_fee")

    return render_template('admin/dashboard.html',
        active_page='admin',
        stats=stats,
        revenue=revenue,
        pending=pending,
        customers=customers,
        packages=packages,
        search=search)


@admin_bp.route('/approve/<int:customer_id>', methods=['POST'])
@login_required
@admin_required
def approve(customer_id):
    db  = get_db()
    cur = db.cursor()

    customer = query_one("""
        SELECT c.*, u.email AS user_email, u.fullname
        FROM tblcustomer c
        LEFT JOIN tbluser u ON u.customer_id = c.idno AND u.role_id IN (1,2)
        WHERE c.idno = %s
    """, [customer_id])

    if not customer:
        flash('ไม่พบข้อมูล', 'danger')
        return redirect(url_for('admin.dashboard'))

    cur.execute("UPDATE tblcustomer SET is_approved = TRUE WHERE idno = %s", [customer_id])
    cur.execute("UPDATE tbluser SET email_verified = TRUE WHERE customer_id = %s", [customer_id])
    db.commit()

    # Send approval email
    try:
        _send(
            customer['user_email'],
            '🎉 บัญชี CondoFront ของคุณได้รับการอนุมัติแล้ว!',
            f"""สวัสดีคุณ {customer['fullname']},

ยินดีด้วย! บัญชี CondoFront ของคุณได้รับการอนุมัติแล้ว

โครงการ: {customer['customer_name']}

เข้าสู่ระบบได้ที่: {request.host_url}auth/login

ทีมงาน CondoFront
Connect. Automate. Optimize.
"""
        )
    except Exception:
        pass

    flash(f'✅ อนุมัติ {customer["customer_name"]} สำเร็จ!', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/reject/<int:customer_id>', methods=['POST'])
@login_required
@admin_required
def reject(customer_id):
    db  = get_db()
    cur = db.cursor()
    customer = query_one("SELECT * FROM tblcustomer WHERE idno = %s", [customer_id])
    cur.execute("UPDATE tblcustomer SET is_active = FALSE WHERE idno = %s", [customer_id])
    cur.execute("UPDATE tbluser SET is_active = FALSE WHERE customer_id = %s", [customer_id])
    db.commit()
    flash(f'ปฏิเสธ {customer["customer_name"] if customer else customer_id} แล้ว', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/suspend/<int:customer_id>', methods=['POST'])
@login_required
@admin_required
def suspend(customer_id):
    """Suspend an approved customer."""
    db  = get_db()
    cur = db.cursor()
    cur.execute("UPDATE tblcustomer SET is_active = FALSE WHERE idno = %s", [customer_id])
    cur.execute("UPDATE tbluser SET is_active = FALSE WHERE customer_id = %s AND role_id != 5", [customer_id])
    db.commit()
    flash('⏸️ ระงับบัญชีลูกค้าแล้ว', 'warning')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/reactivate/<int:customer_id>', methods=['POST'])
@login_required
@admin_required
def reactivate(customer_id):
    """Reactivate a suspended customer."""
    db  = get_db()
    cur = db.cursor()
    cur.execute("UPDATE tblcustomer SET is_active = TRUE WHERE idno = %s", [customer_id])
    cur.execute("UPDATE tbluser SET is_active = TRUE WHERE customer_id = %s AND role_id != 5", [customer_id])
    db.commit()
    flash('✅ เปิดใช้งานบัญชีลูกค้าแล้ว', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/change-package/<int:customer_id>', methods=['POST'])
@login_required
@admin_required
def change_package(customer_id):
    """Change customer's package."""
    package_id = request.form.get('package_id')
    if not package_id:
        flash('กรุณาเลือกแพ็กเกจ', 'danger')
        return redirect(url_for('admin.dashboard'))

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblcustomer SET package_id = %s WHERE idno = %s
    """, [package_id, customer_id])
    cur.execute("""
        UPDATE tblsubscription SET package_id = %s
        WHERE property_id = (
            SELECT idno FROM tblproperty WHERE customer_id = %s LIMIT 1
        )
    """, [package_id, customer_id])
    db.commit()
    flash('📦 เปลี่ยนแพ็กเกจสำเร็จ', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/customer/<int:customer_id>')
@login_required
@admin_required
def customer_detail(customer_id):
    customer = query_one("""
        SELECT c.*, pkg.package_name, pkg.monthly_fee,
               p.property_name, p.idno AS property_id,
               p.address
        FROM tblcustomer c
        LEFT JOIN tblpackage  pkg ON c.package_id  = pkg.idno
        LEFT JOIN tblproperty p   ON p.customer_id = c.idno
        WHERE c.idno = %s
    """, [customer_id])

    if not customer:
        flash('ไม่พบข้อมูลลูกค้า', 'danger')
        return redirect(url_for('admin.dashboard'))

    users = query_all("""
        SELECT u.idno, u.fullname, u.email, u.mobile,
               u.is_active, u.created_at, r.role_name
        FROM tbluser u
        JOIN tblrole r ON u.role_id = r.idno
        WHERE u.customer_id = %s
        ORDER BY u.role_id, u.fullname
    """, [customer_id])

    rooms = query_all("""
        SELECT r.idno, r.building, r.room_no, r.owner_name,
               r.is_active,
               (SELECT COUNT(*) FROM tblparcel p
                WHERE p.room_id = r.idno AND p.status_id = 0) AS waiting_parcels
        FROM tblroom r
        JOIN tblproperty p ON r.property_id = p.idno
        WHERE p.customer_id = %s
        ORDER BY r.building, r.room_no
        LIMIT 50
    """, [customer_id])

    activity = query_one("""
        SELECT
            (SELECT COUNT(*) FROM tblparcel par
             JOIN tblproperty p ON par.property_id = p.idno
             WHERE p.customer_id = %s AND par.deleted_at IS NULL) AS parcels,
            (SELECT COUNT(*) FROM tblvisitor v
             JOIN tblproperty p ON v.property_id = p.idno
             WHERE p.customer_id = %s) AS visitors,
            (SELECT COUNT(*) FROM tblservice_request sr
             JOIN tblproperty p ON sr.property_id = p.idno
             WHERE p.customer_id = %s) AS services,
            (SELECT COUNT(*) FROM tblfacility_booking fb
             JOIN tblproperty p ON fb.property_id = p.idno
             WHERE p.customer_id = %s) AS bookings
    """, [customer_id, customer_id, customer_id, customer_id])

    packages = query_all("""
        SELECT * FROM tblpackage ORDER BY monthly_fee
    """)

    return render_template('admin/customer_detail.html',
        customer=customer,
        users=users,
        rooms=rooms,
        activity=activity,
        packages=packages)


# ── SUBSCRIPTION / PACKAGE MANAGEMENT ───────────────────────

@admin_bp.route('/packages')
@login_required
@admin_required
def packages():
    pkgs = query_all("""
        SELECT p.*,
               (SELECT COUNT(*) FROM tblcustomer c
                WHERE c.package_id = p.idno
                AND c.is_approved = TRUE) AS customer_count
        FROM tblpackage p
        ORDER BY p.monthly_fee
    """)
    return render_template('admin/packages.html', packages=pkgs)


@admin_bp.route('/packages/save', methods=['POST'])
@login_required
@admin_required
def save_package():
    pkg_id      = request.form.get('pkg_id')
    name        = request.form.get('package_name', '').strip()
    monthly_fee = request.form.get('monthly_fee', 0)
    max_room    = request.form.get('max_room', 10)
    max_user    = request.form.get('max_user', 2)
    max_parcel  = request.form.get('max_parcel', 100)
    is_active   = request.form.get('is_active') == 'true'

    if not name:
        flash('กรุณากรอกชื่อแพ็กเกจ', 'danger')
        return redirect(url_for('admin.packages'))

    db  = get_db()
    cur = db.cursor()

    if pkg_id:
        cur.execute("""
            UPDATE tblpackage SET
                package_name = %s, monthly_fee = %s,
                max_room = %s, max_user = %s,
                max_parcel = %s, is_active = %s
            WHERE idno = %s
        """, [name, monthly_fee, max_room, max_user, max_parcel, is_active, pkg_id])
        flash(f'✅ อัปเดตแพ็กเกจ {name} สำเร็จ', 'success')
    else:
        cur.execute("""
            INSERT INTO tblpackage
                (package_name, monthly_fee, max_room, max_user, max_parcel, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, [name, monthly_fee, max_room, max_user, max_parcel, is_active])
        flash(f'✅ เพิ่มแพ็กเกจ {name} สำเร็จ', 'success')

    db.commit()
    return redirect(url_for('admin.packages'))
