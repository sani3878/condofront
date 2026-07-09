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
        SELECT DISTINCT ON (c.idno)
               c.idno, c.customer_name, c.email, c.mobile,
               u.created_at,
               pkg.package_name,
               p.property_name,
               u.fullname,
               (SELECT COUNT(*) FROM tblroom r
                WHERE r.property_id = p.idno) AS room_count
        FROM tblcustomer c
        LEFT JOIN tblpackage  pkg ON c.package_id  = pkg.idno
        LEFT JOIN tblproperty p   ON p.customer_id = c.idno
        LEFT JOIN tbluser     u   ON u.customer_id = c.idno
                                 AND u.role_id = 1
        WHERE c.is_approved = FALSE
        ORDER BY c.idno DESC
    """)

    # All approved customers with filter
    search       = request.args.get('q', '').strip()
    cust_filter  = request.args.get('filter', 'active')

    sql = """
        SELECT DISTINCT ON (c.idno)
               c.idno, c.customer_name, c.email, c.is_active,
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
                AND par.deleted_at IS NULL) AS parcel_count,
               (SELECT MAX(i.created_at) FROM tblinvoice i
                WHERE i.customer_id = c.idno) AS last_invoice_at,
               (SELECT COUNT(*) FROM tblinvoice i
                WHERE i.customer_id = c.idno
                AND i.status = 'unpaid') AS unpaid_count
        FROM tblcustomer c
        LEFT JOIN tblpackage  pkg ON c.package_id  = pkg.idno
        LEFT JOIN tblproperty p   ON p.customer_id = c.idno
        LEFT JOIN tbluser     u   ON u.customer_id = c.idno
                                 AND u.role_id = 1
        WHERE c.is_approved = TRUE
    """
    params = []
    if cust_filter == 'active':
        sql += " AND c.is_active = TRUE"
    elif cust_filter == 'suspended':
        sql += " AND c.is_active = FALSE"
    elif cust_filter == 'unpaid':
        sql += """ AND EXISTS (
            SELECT 1 FROM tblinvoice i
            WHERE i.customer_id = c.idno AND i.status = 'unpaid'
        )"""
    elif cust_filter == 'pending_payment':
        sql += """ AND EXISTS (
            SELECT 1 FROM tblpayment pm
            WHERE pm.customer_id = c.idno AND pm.status = 'pending'
        )"""
    elif cust_filter == 'free':
        sql += " AND (pkg.monthly_fee = 0 OR pkg.monthly_fee IS NULL)"

    if search:
        sql += " AND (c.customer_name ILIKE %s OR c.email ILIKE %s OR p.property_name ILIKE %s)"
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    sql += " ORDER BY c.idno DESC LIMIT 100"
    customers = query_all(sql, params)

    packages = query_all("SELECT * FROM tblpackage WHERE is_active = TRUE ORDER BY monthly_fee")

    return render_template('admin/dashboard.html',
        active_page='admin',
        stats=stats,
        revenue=revenue,
        pending=pending,
        customers=customers,
        packages=packages,
        search=search,
        cust_filter=cust_filter)


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
    pkg_id          = request.form.get('pkg_id')
    name            = request.form.get('package_name', '').strip()
    monthly_fee     = request.form.get('monthly_fee', 0)
    max_room        = request.form.get('max_room', 10)
    max_user        = request.form.get('max_user', 2)
    max_parcel      = request.form.get('max_parcel', 100)
    annual_discount = request.form.get('annual_discount', 10)
    is_active       = request.form.get('is_active') == 'true'

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
                max_parcel = %s, annual_discount = %s,
                is_active = %s
            WHERE idno = %s
        """, [name, monthly_fee, max_room, max_user,
              max_parcel, annual_discount, is_active, pkg_id])
        flash(f'✅ อัปเดตแพ็กเกจ {name} สำเร็จ', 'success')
    else:
        cur.execute("""
            INSERT INTO tblpackage
                (package_name, monthly_fee, max_room, max_user,
                 max_parcel, annual_discount, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, [name, monthly_fee, max_room, max_user,
              max_parcel, annual_discount, is_active])
        flash(f'✅ เพิ่มแพ็กเกจ {name} สำเร็จ', 'success')

    db.commit()
    return redirect(url_for('admin.packages'))


# ── INVOICE ROUTES ───────────────────────────────────────────

@admin_bp.route('/invoices')
@login_required
@admin_required
def invoices():
    status_filter = request.args.get('status', 'all')
    search        = request.args.get('q', '').strip()

    sql = """
        SELECT i.idno, i.invoice_no, i.amount, i.period_start,
               i.period_end, i.due_date, i.status, i.created_at,
               i.paid_at, i.note,
               c.customer_name, c.email,
               p.property_name, pkg.package_name
        FROM tblinvoice i
        JOIN tblcustomer c  ON i.customer_id = c.idno
        LEFT JOIN tblproperty p  ON i.property_id = p.idno
        LEFT JOIN tblpackage pkg ON i.package_id  = pkg.idno
        WHERE 1=1
    """
    params = []
    if status_filter != 'all':
        sql += " AND i.status = %s"
        params.append(status_filter)
    if search:
        sql += " AND (c.customer_name ILIKE %s OR i.invoice_no ILIKE %s)"
        params += [f'%{search}%', f'%{search}%']
    sql += " ORDER BY i.created_at DESC LIMIT 100"

    invoice_list = query_all(sql, params)

    # Stats
    stats = query_one("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'unpaid') AS unpaid,
            COUNT(*) FILTER (WHERE status = 'paid')   AS paid,
            COALESCE(SUM(amount) FILTER (WHERE status = 'paid'
                AND DATE_TRUNC('month', paid_at) = DATE_TRUNC('month', NOW())), 0)
                AS this_month
        FROM tblinvoice
    """)

    customers = query_all("""
        SELECT c.idno, c.customer_name,
               p.idno AS property_id, p.property_name,
               pkg.idno AS package_id, pkg.package_name, pkg.monthly_fee
        FROM tblcustomer c
        LEFT JOIN tblproperty p ON p.customer_id = c.idno
        LEFT JOIN tblpackage pkg ON c.package_id = pkg.idno
        WHERE c.is_approved = TRUE AND c.is_active = TRUE
        ORDER BY c.customer_name
    """)

    return render_template('admin/invoices.html',
        active_page='invoices',
        invoices=invoice_list,
        stats=stats,
        customers=customers,
        status_filter=status_filter,
        search=search)


@admin_bp.route('/invoices/generate', methods=['POST'])
@login_required
@admin_required
def generate_invoice():
    customer_id  = request.form.get('customer_id')
    property_id  = request.form.get('property_id') or None
    package_id   = request.form.get('package_id') or None
    amount       = request.form.get('amount')
    period_start = request.form.get('period_start')
    period_end   = request.form.get('period_end')
    due_date     = request.form.get('due_date')
    note         = request.form.get('note', '').strip() or None

    if not all([customer_id, amount, period_start, period_end, due_date]):
        flash('กรุณากรอกข้อมูลให้ครบ', 'danger')
        return redirect(url_for('admin.invoices'))

    # Generate invoice number
    try:
        last = query_one("SELECT COALESCE(MAX(idno), 0) AS last_num FROM tblinvoice")
        next_num = (last['last_num'] or 0) + 1
    except Exception:
        next_num = 1
    invoice_no = f'INV-{next_num:05d}'

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO tblinvoice
            (customer_id, property_id, package_id, invoice_no,
             amount, period_start, period_end, due_date,
             status, note, created_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'unpaid',%s,%s)
        RETURNING idno
    """, [customer_id, property_id, package_id, invoice_no,
          amount, period_start, period_end, due_date,
          note, current_user.id])
    db.commit()

    flash(f'✅ สร้างใบแจ้งหนี้ {invoice_no} สำเร็จ', 'success')
    return redirect(url_for('admin.invoices'))


@admin_bp.route('/invoices/mark-paid/<int:invoice_id>', methods=['POST'])
@login_required
@admin_required
def mark_invoice_paid(invoice_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblinvoice SET status = 'paid', paid_at = NOW(), paid_by = %s
        WHERE idno = %s
    """, [current_user.id, invoice_id])
    db.commit()
    flash('✅ บันทึกการชำระเงินแล้ว', 'success')
    return redirect(url_for('admin.invoices'))


@admin_bp.route('/invoices/cancel/<int:invoice_id>', methods=['POST'])
@login_required
@admin_required
def cancel_invoice(invoice_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblinvoice SET status = 'cancelled' WHERE idno = %s
    """, [invoice_id])
    db.commit()
    flash('ยกเลิกใบแจ้งหนี้แล้ว', 'success')
    return redirect(url_for('admin.invoices'))


@admin_bp.route('/invoices/print/<int:invoice_id>')
@login_required
@admin_required
def print_invoice(invoice_id):
    invoice = query_one("""
        SELECT i.*, c.customer_name, c.email AS customer_email,
               p.property_name, p.address,
               pkg.package_name,
               u.fullname AS paid_by_name
        FROM tblinvoice i
        JOIN tblcustomer c ON i.customer_id = c.idno
        LEFT JOIN tblproperty p ON i.property_id = p.idno
        LEFT JOIN tblpackage pkg ON i.package_id = pkg.idno
        LEFT JOIN tbluser u ON i.paid_by = u.idno
        WHERE i.idno = %s
    """, [invoice_id])

    if not invoice:
        flash('ไม่พบใบแจ้งหนี้', 'danger')
        return redirect(url_for('admin.invoices'))

    return render_template('admin/invoice_print.html',
        invoice=invoice, hide_navbar=True)


# ── ADMIN ANNOUNCEMENTS ──────────────────────────────────────

@admin_bp.route('/announcements')
@login_required
@admin_required
def announcements():
    """Admin sends system-wide announcements to all customers."""
    return render_template('admin/announcements.html',
        active_page='announcements')


# ── PENDING SLIPS ────────────────────────────────────────────

@admin_bp.route('/slips')
@login_required
@admin_required
def pending_slips():
    """Review payment slips submitted by customers."""
    slips = query_all("""
        SELECT p.idno, p.amount, p.plan_type, p.slip_path,
               p.submitted_at, p.status, p.rejected_reason,
               c.customer_name, c.email,
               pr.property_name,
               pkg.package_name,
               i.invoice_no
        FROM tblpayment p
        JOIN tblcustomer c  ON p.customer_id = c.idno
        LEFT JOIN tblproperty pr ON pr.customer_id = c.idno
        LEFT JOIN tblpackage pkg ON p.package_id = pkg.idno
        LEFT JOIN tblinvoice i   ON i.payment_id = p.idno
        ORDER BY
            CASE p.status WHEN 'pending' THEN 0 ELSE 1 END,
            p.submitted_at DESC
        LIMIT 50
    """)
    return render_template('admin/slips.html',
        active_page='invoices', slips=slips)


@admin_bp.route('/slips/verify/<int:payment_id>', methods=['POST'])
@login_required
@admin_required
def verify_slip(payment_id):
    """Approve payment slip — activate subscription."""
    action = request.form.get('action')  # approve | reject
    reason = request.form.get('reason', '').strip()

    db  = get_db()
    cur = db.cursor()

    payment = query_one("""
        SELECT p.*, c.customer_name,
               pr.idno AS property_id,
               i.idno AS invoice_id
        FROM tblpayment p
        JOIN tblcustomer c ON p.customer_id = c.idno
        LEFT JOIN tblproperty pr ON pr.customer_id = c.idno
        LEFT JOIN tblinvoice i ON i.payment_id = p.idno
        WHERE p.idno = %s
    """, [payment_id])

    if not payment:
        flash('ไม่พบรายการ', 'danger')
        return redirect(url_for('admin.pending_slips'))

    if action == 'approve':
        # Mark payment verified
        cur.execute("""
            UPDATE tblpayment SET
                status = 'verified', verified_at = NOW(), verified_by = %s
            WHERE idno = %s
        """, [current_user.id, payment_id])

        # Mark invoice paid
        if payment['invoice_id']:
            cur.execute("""
                UPDATE tblinvoice SET
                    status = 'paid', paid_at = NOW(), paid_by = %s
                WHERE idno = %s
            """, [current_user.id, payment['invoice_id']])

        # Activate / update subscription
        months = 12 if payment['plan_type'] == 'annual' else 1
        from datetime import date
        end_date = date.today().replace(day=1)
        # Add months
        import calendar
        m = end_date.month + months
        y = end_date.year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        d = min(end_date.day, calendar.monthrange(y, m)[1])
        end_date = date(y, m, d)

        # Check if subscription exists
        existing = query_one("""
            SELECT idno FROM tblsubscription
            WHERE property_id = %s AND is_active = TRUE
        """, [payment['property_id']])

        if existing:
            cur.execute("""
                UPDATE tblsubscription SET
                    package_id = %s, plan_type = %s,
                    start_date = CURRENT_DATE, end_date = %s
                WHERE idno = %s
            """, [payment['package_id'], payment['plan_type'],
                  end_date, existing['idno']])
        else:
            cur.execute("""
                INSERT INTO tblsubscription
                    (property_id, package_id, plan_type,
                     start_date, end_date, is_active)
                VALUES (%s,%s,%s,CURRENT_DATE,%s,TRUE)
            """, [payment['property_id'], payment['package_id'],
                  payment['plan_type'], end_date])

        # Update customer package
        cur.execute("""
            UPDATE tblcustomer SET package_id = %s
            WHERE idno = %s
        """, [payment['package_id'], payment['customer_id']])

        db.commit()

        # Send confirmation email
        try:
            customer = query_one("""
                SELECT c.email, c.customer_name,
                       pkg.package_name, pr.property_name
                FROM tblcustomer c
                LEFT JOIN tblpackage pkg ON c.package_id = pkg.idno
                LEFT JOIN tblproperty pr ON pr.customer_id = c.idno
                WHERE c.idno = %s
            """, [payment['customer_id']])
            if customer:
                _send(
                    customer['email'],
                    '✅ ยืนยันการชำระเงิน — CondoFront',
                    f"""สวัสดีคุณ {customer['customer_name']},

ยืนยันการชำระเงินเรียบร้อยแล้ว! 🎉

แพ็กเกจ: {customer['package_name']}
โครงการ: {customer['property_name']}
วันหมดอายุ: {end_date.strftime('%d/%m/%Y')}

ขอบคุณที่ไว้วางใจ CondoFront!
Connect. Automate. Optimize.
"""
                )
        except Exception:
            pass

        flash(f'✅ อนุมัติการชำระเงินและอัปเดตแพ็กเกจสำเร็จ', 'success')

    else:  # reject
        cur.execute("""
            UPDATE tblpayment SET
                status = 'rejected', verified_at = NOW(),
                verified_by = %s, rejected_reason = %s
            WHERE idno = %s
        """, [current_user.id, reason or 'ไม่ระบุ', payment_id])
        db.commit()
        flash('❌ ปฏิเสธการชำระเงินแล้ว', 'warning')

    return redirect(url_for('admin.pending_slips'))


# ── EMAIL INVOICE ────────────────────────────────────────────

@admin_bp.route('/invoices/email/<int:invoice_id>', methods=['POST'])
@login_required
@admin_required
def email_invoice(invoice_id):
    """Email invoice to customer."""
    invoice = query_one("""
        SELECT i.*, c.customer_name, c.email,
               p.property_name, pkg.package_name
        FROM tblinvoice i
        JOIN tblcustomer c ON i.customer_id = c.idno
        LEFT JOIN tblproperty p ON i.property_id = p.idno
        LEFT JOIN tblpackage pkg ON i.package_id = pkg.idno
        WHERE i.idno = %s
    """, [invoice_id])

    if not invoice:
        flash('ไม่พบใบแจ้งหนี้', 'danger')
        return redirect(url_for('admin.invoices'))

    try:
        print_url = url_for('admin.print_invoice',
                            invoice_id=invoice_id, _external=True)
        _send(
            invoice['email'],
            f'🧾 ใบแจ้งหนี้ {invoice["invoice_no"]} — CondoFront',
            f"""สวัสดีคุณ {invoice['customer_name']},

กรุณาชำระค่าบริการ CondoFront

เลขใบแจ้งหนี้ : {invoice['invoice_no']}
แพ็กเกจ      : {invoice['package_name'] or '-'}
ยอดชำระ      : ฿{invoice['amount']:,.2f}
กำหนดชำระ    : {invoice['due_date'].strftime('%d/%m/%Y') if invoice['due_date'] else '-'}

ดูใบแจ้งหนี้: {print_url}

ชำระผ่าน PromptPay และอัปโหลดสลิปได้ที่:
{request.host_url}billing/upgrade

ขอบคุณ,
ทีมงาน CondoFront
Connect. Automate. Optimize.
"""
        )
        flash(f'📧 ส่งใบแจ้งหนี้ไปที่ {invoice["email"]} แล้ว', 'success')
    except Exception as e:
        flash(f'ส่งอีเมลไม่สำเร็จ: {str(e)}', 'danger')

    return redirect(url_for('admin.invoices'))


# ── CUSTOMER NOTES ───────────────────────────────────────────

@admin_bp.route('/customer/<int:customer_id>/note', methods=['POST'])
@login_required
@admin_required
def save_note(customer_id):
    """Save internal admin note for customer."""
    note = request.form.get('note', '').strip()
    db   = get_db()
    cur  = db.cursor()
    cur.execute("UPDATE tblcustomer SET notes = %s WHERE idno = %s",
                [note or None, customer_id])
    db.commit()
    flash('บันทึกโน้ตแล้ว', 'success')
    return redirect(url_for('admin.customer_detail', customer_id=customer_id))


# ── IMPERSONATE ──────────────────────────────────────────────

@admin_bp.route('/impersonate/<int:user_id>')
@login_required
@admin_required
def impersonate(user_id):
    """Login as a customer user to see their view."""
    from flask_login import login_user
    from ..models import User

    target = query_one("""
        SELECT u.*, r.role_name FROM tbluser u
        JOIN tblrole r ON u.role_id = r.idno
        WHERE u.idno = %s AND u.role_id != 5
    """, [user_id])

    if not target:
        flash('ไม่พบผู้ใช้', 'danger')
        return redirect(url_for('admin.dashboard'))

    # Store admin session so we can return
    from flask import session
    session['admin_id'] = current_user.id

    user = User(target)
    login_user(user)
    flash(f'👁 กำลังดูในมุมมองของ {target["fullname"]} — '
          f'<a href="{url_for("admin.stop_impersonate")}">กลับ Admin</a>', 'warning')
    return redirect(url_for('main.home'))


@admin_bp.route('/impersonate/stop')
@login_required
def stop_impersonate():
    """Return to admin session."""
    from flask import session
    from flask_login import login_user
    from ..models import User

    admin_id = session.pop('admin_id', None)
    if not admin_id:
        return redirect(url_for('main.home'))

    admin = query_one("SELECT * FROM tbluser WHERE idno = %s", [admin_id])
    if admin:
        login_user(User(admin))

    return redirect(url_for('admin.dashboard'))
