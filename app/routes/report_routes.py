from datetime import datetime, date
from flask import render_template, request
from flask_login import login_required, current_user
from ..blueprints import report_bp
from ..helpers import query_one, query_all
from ..decorators import staff_required


@report_bp.route('/')
@login_required
@staff_required
def dashboard():
    pid = current_user.property_id

    # ── TODAY ──────────────────────────────────────────────
    today_received = query_one("""
        SELECT COUNT(*) AS cnt FROM tblparcel
        WHERE property_id = %s
          AND DATE(received_at) = CURRENT_DATE
          AND deleted_at IS NULL
    """, [pid])['cnt']

    today_picked = query_one("""
        SELECT COUNT(*) AS cnt FROM tblparcel
        WHERE property_id = %s
          AND status_id = 1
          AND DATE(updated_at) = CURRENT_DATE
          AND deleted_at IS NULL
    """, [pid])['cnt']

    # Pickup method breakdown — total all time
    pickup_by_method = query_all("""
        SELECT pk.pickup_method,
               COUNT(*) AS cnt
        FROM tblpickup pk
        JOIN tblparcel p ON pk.parcel_id = p.idno
        WHERE p.property_id = %s
        GROUP BY pk.pickup_method
    """, [pid])

    pickup_qr     = next((r['cnt'] for r in pickup_by_method if r['pickup_method'] == 'qr'), 0)
    pickup_manual = next((r['cnt'] for r in pickup_by_method if r['pickup_method'] == 'manual'), 0)

    today_waiting = query_one("""
        SELECT COUNT(*) AS cnt FROM tblparcel
        WHERE property_id = %s
          AND status_id = 0
          AND deleted_at IS NULL
    """, [pid])['cnt']

    today_overdue = query_one("""
        SELECT COUNT(*) AS cnt FROM tblparcel
        WHERE property_id = %s
          AND status_id = 0
          AND received_at < NOW() - INTERVAL '3 days'
          AND deleted_at IS NULL
    """, [pid])['cnt']

    # ── WAITING LIST ───────────────────────────────────────
    waiting = query_all("""
        SELECT p.idno, p.received_at, p.tracking_no, p.note,
               r.room_no, r.building,
               c.courier_name,
               EXTRACT(DAY FROM NOW() - p.received_at)::int AS days_waiting
        FROM tblparcel p
        JOIN tblroom r ON p.room_id = r.idno
        LEFT JOIN tblcourier c ON p.courier_id = c.idno
        WHERE p.property_id = %s
          AND p.status_id = 0
          AND p.deleted_at IS NULL
        ORDER BY p.received_at ASC
    """, [pid])

    # ── MONTHLY ────────────────────────────────────────────
    # month selector
    now = datetime.now()
    sel_year  = request.args.get('year',  now.year,  type=int)
    sel_month = request.args.get('month', now.month, type=int)

    monthly_total = query_one("""
        SELECT COUNT(*) AS cnt FROM tblparcel
        WHERE property_id = %s
          AND EXTRACT(YEAR  FROM received_at) = %s
          AND EXTRACT(MONTH FROM received_at) = %s
          AND deleted_at IS NULL
    """, [pid, sel_year, sel_month])['cnt']

    monthly_picked = query_one("""
        SELECT COUNT(*) AS cnt FROM tblparcel
        WHERE property_id = %s
          AND status_id = 1
          AND EXTRACT(YEAR  FROM received_at) = %s
          AND EXTRACT(MONTH FROM received_at) = %s
          AND deleted_at IS NULL
    """, [pid, sel_year, sel_month])['cnt']

    monthly_waiting = query_one("""
        SELECT COUNT(*) AS cnt FROM tblparcel
        WHERE property_id = %s
          AND status_id = 0
          AND EXTRACT(YEAR  FROM received_at) = %s
          AND EXTRACT(MONTH FROM received_at) = %s
          AND deleted_at IS NULL
    """, [pid, sel_year, sel_month])['cnt']

    # By courier this month
    by_courier = query_all("""
        SELECT COALESCE(c.courier_name, 'ไม่ระบุ') AS courier_name,
               COUNT(*) AS cnt
        FROM tblparcel p
        LEFT JOIN tblcourier c ON p.courier_id = c.idno
        WHERE p.property_id = %s
          AND EXTRACT(YEAR  FROM p.received_at) = %s
          AND EXTRACT(MONTH FROM p.received_at) = %s
          AND p.deleted_at IS NULL
        GROUP BY c.courier_name
        ORDER BY cnt DESC
    """, [pid, sel_year, sel_month])

    # Daily trend this month (for mini chart)
    daily_trend = query_all("""
        SELECT EXTRACT(DAY FROM received_at)::int AS day,
               COUNT(*) AS cnt
        FROM tblparcel
        WHERE property_id = %s
          AND EXTRACT(YEAR  FROM received_at) = %s
          AND EXTRACT(MONTH FROM received_at) = %s
          AND deleted_at IS NULL
        GROUP BY day
        ORDER BY day
    """, [pid, sel_year, sel_month])

    # Build month options (last 12 months)
    month_options = []
    for i in range(12):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        month_options.append({'year': y, 'month': m})

    thai_months = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
                   'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']

    return render_template('report/dashboard.html',
        active_page='report',
        now=now,
        today_received=today_received,
        today_picked=today_picked,
        today_waiting=today_waiting,
        today_overdue=today_overdue,
        pickup_qr=pickup_qr,
        pickup_manual=pickup_manual,
        waiting=waiting,
        monthly_total=monthly_total,
        monthly_picked=monthly_picked,
        monthly_waiting=monthly_waiting,
        by_courier=by_courier,
        daily_trend=daily_trend,
        sel_year=sel_year,
        sel_month=sel_month,
        month_options=month_options,
        thai_months=thai_months,
    )
