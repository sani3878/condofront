import os, secrets
from datetime import date, timedelta
from decimal import Decimal
from flask import (render_template, request, redirect, url_for,
                   flash, current_app, jsonify)
from flask_login import login_required, current_user
from ..blueprints import billing_bp
from ..helpers import query_all, query_one, get_db
from ..mail import _send
from ..decorators import staff_required, resident_required


ANNUAL_DISCOUNT = Decimal('0.10')  # default fallback only


def calc_price(monthly_fee, plan_type, annual_discount=10):
    """Calculate price based on plan type and package discount."""
    fee      = Decimal(str(monthly_fee or 0))
    discount = Decimal(str(annual_discount or 10)) / 100

    if plan_type == 'annual' and discount > 0:
        total   = fee * 12 * (1 - discount)
        per_mo  = total / 12
        savings = fee * 12 * discount
        return {
            'amount':   total.quantize(Decimal('0.01')),
            'per_mo':   per_mo.quantize(Decimal('0.01')),
            'savings':  savings.quantize(Decimal('0.01')),
            'months':   12,
            'discount': int(annual_discount),
            'label':    f'Annual ({int(annual_discount)}% off)',
        }
    else:
        return {
            'amount':   fee.quantize(Decimal('0.01')),
            'per_mo':   fee.quantize(Decimal('0.01')),
            'savings':  Decimal('0'),
            'months':   1,
            'discount': 0,
            'label':    'Monthly',
        }


# ── UPGRADE PAGE ─────────────────────────────────────────────

@billing_bp.route('/upgrade')
@login_required
@staff_required
def upgrade():
    if current_user.is_resident or current_user.is_superadmin:
        return redirect(url_for('main.home'))

    packages = query_all("""
        SELECT * FROM tblpackage
        WHERE is_active = TRUE
        ORDER BY monthly_fee
    """)

    current_sub = query_one("""
        SELECT s.*, pkg.package_name, pkg.monthly_fee,
               COALESCE(s.plan_type, 'monthly') AS plan_type
        FROM tblsubscription s
        JOIN tblpackage pkg ON s.package_id = pkg.idno
        WHERE s.property_id = %s AND s.is_active = TRUE
        ORDER BY s.idno DESC LIMIT 1
    """, [current_user.property_id])

    return render_template('billing/upgrade.html',
        packages=packages,
        current_sub=current_sub)


@billing_bp.route('/checkout', methods=['POST'])
@login_required
@staff_required
def checkout():
    """Show payment QR + invoice preview."""
    package_id = request.form.get('package_id')
    plan_type  = request.form.get('plan_type', 'monthly')

    if not package_id:
        flash('กรุณาเลือกแพ็กเกจ', 'danger')
        return redirect(url_for('billing.upgrade'))

    pkg = query_one("""
        SELECT * FROM tblpackage WHERE idno = %s AND is_active = TRUE
    """, [package_id])

    if not pkg:
        flash('ไม่พบแพ็กเกจ', 'danger')
        return redirect(url_for('billing.upgrade'))

    annual_discount = float(pkg.get('annual_discount') or 10)
    price_info = calc_price(pkg['monthly_fee'], plan_type, annual_discount)

    # Generate invoice number safely
    try:
        last = query_one("""
            SELECT COALESCE(MAX(idno), 0) AS n FROM tblinvoice
        """)
        next_num = (last['n'] or 0) + 1
    except Exception:
        next_num = 1
    invoice_no = f'INV-{next_num:05d}'

    # Period dates
    today      = date.today()
    if plan_type == 'annual':
        period_end = date(today.year + 1, today.month, today.day) - timedelta(days=1)
    else:
        next_month = today.replace(day=1) + timedelta(days=32)
        period_end = next_month.replace(day=1) - timedelta(days=1)

    due_date = today + timedelta(days=7)

    promptpay_id = current_app.config.get('PROMPTPAY_ID', '0000000000')

    return render_template('billing/checkout.html',
        pkg=pkg,
        plan_type=plan_type,
        price_info=price_info,
        invoice_no=invoice_no,
        period_start=today,
        period_end=period_end,
        due_date=due_date,
        promptpay_id=promptpay_id)


@billing_bp.route('/submit-payment', methods=['POST'])
@login_required
@staff_required
def submit_payment():
    """Customer submits payment slip."""
    package_id   = request.form.get('package_id')
    plan_type    = request.form.get('plan_type', 'monthly')
    amount       = request.form.get('amount')
    invoice_no   = request.form.get('invoice_no')
    period_start = request.form.get('period_start')
    period_end   = request.form.get('period_end')
    due_date     = request.form.get('due_date')

    # Handle slip upload
    slip_path = None
    if 'slip' in request.files:
        slip = request.files['slip']
        if slip and slip.filename:
            ext       = os.path.splitext(slip.filename)[1].lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.pdf'):
                flash('กรุณาอัปโหลดไฟล์ JPG, PNG หรือ PDF เท่านั้น', 'danger')
                return redirect(url_for('billing.upgrade'))
            fname     = f"slip_{current_user.id}_{secrets.token_urlsafe(8)}{ext}"
            save_path = os.path.join(
                current_app.root_path, 'static', 'uploads', 'slips', fname)
            slip.save(save_path)
            slip_path = f'uploads/slips/{fname}'

    db  = get_db()
    cur = db.cursor()

    # Create invoice
    cur.execute("""
        INSERT INTO tblinvoice
            (customer_id, property_id, package_id, invoice_no,
             amount, period_start, period_end, due_date,
             status, created_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'unpaid',%s)
        RETURNING idno
    """, [current_user.customer_id, current_user.property_id,
          package_id, invoice_no, amount,
          period_start, period_end, due_date,
          current_user.id])
    invoice_id = cur.fetchone()['idno']

    # Create payment record
    cur.execute("""
        INSERT INTO tblpayment
            (invoice_id, customer_id, package_id,
             plan_type, amount, slip_path, status)
        VALUES (%s,%s,%s,%s,%s,%s,'pending')
        RETURNING idno
    """, [invoice_id, current_user.customer_id,
          package_id, plan_type, amount, slip_path])
    payment_id = cur.fetchone()['idno']

    # Link payment to invoice
    cur.execute("""
        UPDATE tblinvoice SET payment_id = %s WHERE idno = %s
    """, [payment_id, invoice_id])

    db.commit()

    flash('✅ ส่งหลักฐานการชำระเงินแล้ว! ทีมงานจะตรวจสอบและยืนยันภายใน 24 ชั่วโมง', 'success')
    return redirect(url_for('billing.history'))


# ── BILLING HISTORY ─────────────────────────────────────────

@billing_bp.route('/history')
@login_required
@staff_required
def history():
    if current_user.is_resident or current_user.is_superadmin:
        return redirect(url_for('main.home'))

    invoices = query_all("""
        SELECT i.idno, i.invoice_no, i.amount, i.period_start,
               i.period_end, i.due_date, i.status, i.created_at,
               i.paid_at, pkg.package_name,
               p.status AS payment_status, p.slip_path,
               p.submitted_at, p.rejected_reason
        FROM tblinvoice i
        LEFT JOIN tblpackage pkg ON i.package_id = pkg.idno
        LEFT JOIN tblpayment p   ON i.payment_id = p.idno
        WHERE i.customer_id = %s
        ORDER BY i.created_at DESC
        LIMIT 24
    """, [current_user.customer_id])

    current_sub = query_one("""
        SELECT s.*, pkg.package_name, pkg.monthly_fee,
               pkg.max_room, pkg.max_property,
               COALESCE(s.plan_type, 'monthly') AS plan_type
        FROM tblsubscription s
        JOIN tblpackage pkg ON s.package_id = pkg.idno
        WHERE s.property_id = %s AND s.is_active = TRUE
        ORDER BY s.idno DESC LIMIT 1
    """, [current_user.property_id])

    return render_template('billing/history.html',
        invoices=invoices,
        current_sub=current_sub)


# ── PROMPTPAY QR GENERATOR ───────────────────────────────────

@billing_bp.route('/promptpay-qr')
@login_required
@staff_required
def promptpay_qr():
    """Generate a real EMVCo PromptPay QR code image."""
    import io, base64
    from promptpay import qrcode as ppqr

    amount     = request.args.get('amount', '0')
    invoice_no = request.args.get('ref', '')
    promptpay_id = current_app.config.get('PROMPTPAY_ID', '0000000000')

    try:
        # Generate proper EMVCo payload
        payload = ppqr.generate_payload(
            promptpay_id,
            amount=float(amount)
        )

        # Generate QR code image
        import qrcode as qr_lib
        from qrcode.image.pil import PilImage

        qr = qr_lib.QRCode(
            version=1,
            error_correction=qr_lib.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(payload)
        qr.make(fit=True)

        img = qr.make_image(fill_color='#1e3a5f', back_color='white')

        # Convert to base64 PNG
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        return jsonify({
            'ok': True,
            'payload': payload,
            'image':   f'data:image/png;base64,{img_b64}',
            'ref':     invoice_no
        })

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@billing_bp.route('/invoice/print/<int:invoice_id>')
@login_required
@staff_required
def print_invoice(invoice_id):
    """Customer prints their own invoice."""
    invoice = query_one("""
        SELECT i.*, c.customer_name, c.email AS customer_email,
               p.property_name, p.address,
               pkg.package_name
        FROM tblinvoice i
        JOIN tblcustomer c  ON i.customer_id = c.idno
        LEFT JOIN tblproperty p  ON i.property_id = p.idno
        LEFT JOIN tblpackage pkg ON i.package_id  = pkg.idno
        WHERE i.idno = %s AND i.customer_id = %s
    """, [invoice_id, current_user.customer_id])

    if not invoice:
        flash('ไม่พบใบแจ้งหนี้', 'danger')
        return redirect(url_for('billing.history'))

    return render_template('admin/invoice_print.html',
        invoice=invoice, hide_navbar=True)
