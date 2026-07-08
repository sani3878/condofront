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
    # Pending approvals
    pending = query_all("""
        SELECT c.idno, c.customer_name, c.email, c.mobile,
               c.is_approved, c.package_id,
               pkg.package_name,
               p.property_name,
               u.fullname, u.created_at
        FROM tblcustomer c
        LEFT JOIN tblpackage pkg ON c.package_id = pkg.idno
        LEFT JOIN tblproperty p  ON p.customer_id = c.idno
        LEFT JOIN tbluser u      ON u.customer_id = c.idno AND u.role_id = 2
        WHERE c.is_approved = FALSE
        ORDER BY c.idno DESC
    """)

    approved = query_all("""
        SELECT c.idno, c.customer_name, c.email,
               pkg.package_name,
               p.property_name,
               u.fullname
        FROM tblcustomer c
        LEFT JOIN tblpackage pkg ON c.package_id = pkg.idno
        LEFT JOIN tblproperty p  ON p.customer_id = c.idno
        LEFT JOIN tbluser u      ON u.customer_id = c.idno AND u.role_id = 2
        WHERE c.is_approved = TRUE
        ORDER BY c.idno DESC
        LIMIT 20
    """)

    return render_template('admin/dashboard.html',
        pending=pending,
        approved=approved)


@admin_bp.route('/approve/<int:customer_id>', methods=['POST'])
@login_required
@admin_required
def approve(customer_id):
    db  = get_db()
    cur = db.cursor()

    customer = query_one("""
        SELECT c.*, u.email, u.fullname
        FROM tblcustomer c
        JOIN tbluser u ON u.customer_id = c.idno AND u.role_id = 2
        WHERE c.idno = %s
    """, [customer_id])

    if not customer:
        flash('ไม่พบข้อมูล', 'danger')
        return redirect(url_for('admin.dashboard'))

    cur.execute("""
        UPDATE tblcustomer SET is_approved = TRUE WHERE idno = %s
    """, [customer_id])
    db.commit()

    # Send approval email to customer
    approve_url = request.host_url + 'auth/login'
    _send(
        customer['email'],
        'บัญชี CondoFront ของคุณได้รับการอนุมัติแล้ว! 🎉',
        f"""สวัสดีคุณ {customer['fullname']},

ยินดีด้วย! บัญชี CondoFront ของคุณได้รับการอนุมัติแล้ว

โครงการ: {customer['customer_name']}

คลิกลิงก์ด้านล่างเพื่อเข้าสู่ระบบ:
{approve_url}

ทีมงาน CondoFront
"""
    )

    flash(f'อนุมัติ {customer["customer_name"]} สำเร็จ! ส่งอีเมลแจ้งลูกค้าแล้ว', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/reject/<int:customer_id>', methods=['POST'])
@login_required
@admin_required
def reject(customer_id):
    db  = get_db()
    cur = db.cursor()

    customer = query_one("""
        SELECT c.*, u.email, u.fullname
        FROM tblcustomer c
        JOIN tbluser u ON u.customer_id = c.idno AND u.role_id = 2
        WHERE c.idno = %s
    """, [customer_id])

    # Soft delete — deactivate customer and user
    cur.execute("UPDATE tblcustomer SET is_active = FALSE WHERE idno = %s", [customer_id])
    cur.execute("UPDATE tbluser SET is_active = FALSE WHERE customer_id = %s", [customer_id])
    db.commit()

    flash(f'ปฏิเสธ {customer["customer_name"] if customer else customer_id} แล้ว', 'success')
    return redirect(url_for('admin.dashboard'))
