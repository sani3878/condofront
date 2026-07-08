from datetime import date, datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..blueprints import facility_bp
from ..helpers import query_one, query_all, get_db

# ── DEFAULT FACILITIES ───────────────────────────────────────
DEFAULT_FACILITIES = [
    ('🏊', 'สระว่ายน้ำ',      'Pool',          False, '06:00', '22:00', 60,  20,   False, 0,   'free'),
    ('🏋️', 'ห้องออกกำลังกาย', 'Gym',           False, '06:00', '22:00', 60,  20,   False, 0,   'free'),
    ('🏢', 'ห้องประชุม',       'Meeting Room',  True,  '09:00', '20:00', 60,  1,    True,  200, 'cash'),
    ('🍖', 'บาร์บีคิว',        'BBQ Area',      True,  '10:00', '21:00', 120, 1,    True,  500, 'cash'),
    ('🧘', 'ห้องโยคะ',         'Yoga Room',     True,  '07:00', '20:00', 60,  None, False, 0,   'free'),
    ('🎱', 'ห้องสนุกเกอร์',    'Snooker Room',  True,  '10:00', '22:00', 60,  1,    False, 0,   'free'),
    ('⛳', 'ห้องกอล์ฟ',        'Golf Simulator',True,  '09:00', '21:00', 60,  1,    False, 300, 'cash'),
    ('🧒', 'ห้องเด็ก',         'Kids Room',     False, '08:00', '20:00', 60,  None, False, 0,   'free'),
    ('🎬', 'ห้องดูหนัง',       'Theatre Room',  True,  '10:00', '22:00', 120, 1,    True,  300, 'cash'),
    ('🎮', 'ห้องเกม',          'Game Room',     True,  '10:00', '22:00', 60,  None, False, 0,   'free'),
    ('🎾', 'สนามเทนนิส',       'Tennis Court',  True,  '06:00', '20:00', 60,  1,    False, 0,   'free'),
    ('🏓', 'ปิงปอง',           'Table Tennis',  True,  '08:00', '22:00', 60,  2,    False, 0,   'free'),
    ('🛁', 'ซาวน่า/สตีม',      'Sauna/Steam',   True,  '08:00', '21:00', 60,  None, False, 0,   'free'),
]


def seed_facilities(property_id):
    """Auto-create default facilities for a new property."""
    existing = query_one("""
        SELECT COUNT(*) AS cnt FROM tblfacility WHERE property_id = %s
    """, [property_id])
    if existing and existing['cnt'] > 0:
        return

    db  = get_db()
    cur = db.cursor()
    for i, (icon, name, name_en, booking_req, open_t, close_t,
            slot_mins, capacity, approval, fee, pay_method) in enumerate(DEFAULT_FACILITIES):
        cur.execute("""
            INSERT INTO tblfacility
                (property_id, name, name_en, icon, is_active,
                 booking_required, opening_time, closing_time,
                 slot_duration_mins, max_capacity, approval_required,
                 fee_amount, payment_method, sort_order)
            VALUES (%s,%s,%s,%s, FALSE,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, [property_id, name, name_en, icon,
              booking_req, open_t, close_t,
              slot_mins, capacity, approval,
              fee, pay_method, i])
    db.commit()


def get_time_slots(facility, for_date):
    """Generate available time slots for a facility on a given date."""
    if not facility['booking_required']:
        return []

    slots = []
    current = datetime.strptime(str(facility['opening_time']), '%H:%M:%S')
    closing = datetime.strptime(str(facility['closing_time']), '%H:%M:%S')
    duration = timedelta(minutes=facility['slot_duration_mins'])

    while current + duration <= closing:
        end_time = current + duration
        slots.append({
            'start': current.strftime('%H:%M'),
            'end':   end_time.strftime('%H:%M'),
        })
        current = end_time

    return slots


def get_slot_bookings(facility_id, booking_date):
    """Get booking counts per slot for conflict checking."""
    bookings = query_all("""
        SELECT start_time, COUNT(*) AS cnt, unit_id
        FROM tblfacility_booking
        WHERE facility_id = %s
          AND booking_date = %s
          AND status != 'cancelled'
        GROUP BY start_time, unit_id
    """, [facility_id, booking_date])
    return bookings


# ── STAFF ROUTES ────────────────────────────────────────────

@facility_bp.route('/')
@login_required
def dashboard():
    if current_user.is_resident:
        return redirect(url_for('facility.resident_facilities'))

    seed_facilities(current_user.property_id)

    facilities = query_all("""
        SELECT * FROM tblfacility
        WHERE property_id = %s
        ORDER BY sort_order, name
    """, [current_user.property_id])

    # Today's bookings count
    today_bookings = query_one("""
        SELECT COUNT(*) AS cnt FROM tblfacility_booking
        WHERE property_id = %s
          AND booking_date = CURRENT_DATE
          AND status != 'cancelled'
    """, [current_user.property_id])['cnt']

    # Pending approvals
    pending = query_one("""
        SELECT COUNT(*) AS cnt FROM tblfacility_booking
        WHERE property_id = %s AND status = 'pending'
    """, [current_user.property_id])['cnt']

    return render_template('facility/dashboard.html',
        active_page='facility',
        facilities=facilities,
        today_bookings=today_bookings,
        pending=pending)


@facility_bp.route('/toggle/<int:facility_id>', methods=['POST'])
@login_required
def toggle_facility(facility_id):
    """Quick toggle active status from dashboard."""
    facility = query_one("""
        SELECT idno, is_active FROM tblfacility
        WHERE idno = %s AND property_id = %s
    """, [facility_id, current_user.property_id])

    if not facility:
        flash('ไม่พบข้อมูล', 'danger')
        return redirect(url_for('facility.dashboard'))

    new_status = not facility['is_active']
    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblfacility SET is_active = %s
        WHERE idno = %s AND property_id = %s
    """, [new_status, facility_id, current_user.property_id])
    db.commit()

    if new_status:
        # Turning ON → redirect to settings to configure
        flash(f'เปิดใช้งานแล้ว! กรุณาตั้งค่าให้เรียบร้อย', 'success')
        return redirect(url_for('facility.settings') + f'#f{facility_id}')
    else:
        flash(f'ปิดใช้งานแล้ว — ลูกบ้านจะไม่เห็นสิ่งอำนวยความสะดวกนี้', 'success')
        return redirect(url_for('facility.dashboard'))



@facility_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Staff manages facility settings."""
    if current_user.is_resident:
        return redirect(url_for('resident.home'))

    seed_facilities(current_user.property_id)

    if request.method == 'POST':
        facility_id  = request.form.get('facility_id')
        is_active    = request.form.get('is_active') == 'true'
        booking_req  = request.form.get('booking_required') == 'true'
        open_time    = request.form.get('opening_time', '06:00')
        close_time   = request.form.get('closing_time', '22:00')
        slot_mins    = int(request.form.get('slot_duration_mins', 60))
        max_cap      = request.form.get('max_capacity') or None
        approval_req = request.form.get('approval_required') == 'true'
        fee          = request.form.get('fee_amount') or 0
        pay_method   = request.form.get('payment_method', 'free')

        db  = get_db()
        cur = db.cursor()
        cur.execute("""
            UPDATE tblfacility SET
                is_active         = %s,
                booking_required  = %s,
                opening_time      = %s,
                closing_time      = %s,
                slot_duration_mins= %s,
                max_capacity      = %s,
                approval_required = %s,
                fee_amount        = %s,
                payment_method    = %s
            WHERE idno = %s AND property_id = %s
        """, [is_active, booking_req, open_time, close_time,
              slot_mins, max_cap, approval_req, fee, pay_method,
              facility_id, current_user.property_id])
        db.commit()
        flash('บันทึกการตั้งค่าสำเร็จ', 'success')
        return redirect(url_for('facility.settings'))

    facilities = query_all("""
        SELECT * FROM tblfacility
        WHERE property_id = %s
        ORDER BY sort_order, name
    """, [current_user.property_id])

    return render_template('facility/settings.html',
        active_page='facility',
        facilities=facilities)


@facility_bp.route('/bookings')
@login_required
def bookings():
    """Staff views all bookings."""
    if current_user.is_resident:
        return redirect(url_for('resident.home'))

    filter_date   = request.args.get('date', date.today().isoformat())
    filter_status = request.args.get('status', 'all')

    sql = """
        SELECT b.idno, b.booking_date, b.start_time, b.end_time,
               b.status, b.fee_amount, b.fee_paid, b.payment_method,
               b.note, b.created_at,
               f.name AS facility_name, f.icon,
               r.room_no, r.building,
               u.fullname AS booked_by_name
        FROM tblfacility_booking b
        JOIN tblfacility f ON b.facility_id = f.idno
        JOIN tblroom r     ON b.unit_id = r.idno
        JOIN tbluser u     ON b.booked_by = u.idno
        WHERE b.property_id = %s
          AND b.booking_date = %s
    """
    params = [current_user.property_id, filter_date]

    if filter_status != 'all':
        sql += " AND b.status = %s"
        params.append(filter_status)

    sql += " ORDER BY b.start_time ASC"
    booking_list = query_all(sql, params)

    pending_count = query_one("""
        SELECT COUNT(*) AS cnt FROM tblfacility_booking
        WHERE property_id = %s AND status = 'pending'
    """, [current_user.property_id])['cnt']

    return render_template('facility/bookings.html',
        active_page='facility',
        bookings=booking_list,
        filter_date=filter_date,
        filter_status=filter_status,
        pending_count=pending_count)


@facility_bp.route('/approve/<int:booking_id>', methods=['POST'])
@login_required
def approve_booking(booking_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblfacility_booking SET status = 'confirmed'
        WHERE idno = %s AND property_id = %s
    """, [booking_id, current_user.property_id])
    db.commit()
    flash('อนุมัติการจองสำเร็จ', 'success')
    return redirect(url_for('facility.bookings'))


@facility_bp.route('/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblfacility_booking SET
            status       = 'cancelled',
            cancelled_by = %s,
            cancelled_at = NOW()
        WHERE idno = %s AND property_id = %s
    """, [current_user.id, booking_id, current_user.property_id])
    db.commit()
    flash('ยกเลิกการจองแล้ว', 'success')
    return redirect(request.referrer or url_for('facility.bookings'))


@facility_bp.route('/mark-paid/<int:booking_id>', methods=['POST'])
@login_required
def mark_paid(booking_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblfacility_booking SET fee_paid = TRUE
        WHERE idno = %s AND property_id = %s
    """, [booking_id, current_user.property_id])
    db.commit()
    flash('บันทึกการชำระเงินแล้ว ✅', 'success')
    return redirect(request.referrer or url_for('facility.bookings'))


# ── RESIDENT ROUTES ─────────────────────────────────────────

@facility_bp.route('/book')
@login_required
def resident_facilities():
    """Resident sees all active facilities."""
    if not current_user.is_resident:
        return redirect(url_for('facility.dashboard'))

    facilities = query_all("""
        SELECT * FROM tblfacility
        WHERE property_id = %s AND is_active = TRUE
        ORDER BY sort_order, name
    """, [current_user.property_id])

    return render_template('facility/resident_list.html',
        facilities=facilities)


@facility_bp.route('/book/<int:facility_id>', methods=['GET', 'POST'])
@login_required
def book(facility_id):
    """Resident books a facility slot."""
    if not current_user.is_resident:
        return redirect(url_for('facility.dashboard'))

    facility = query_one("""
        SELECT * FROM tblfacility
        WHERE idno = %s AND property_id = %s AND is_active = TRUE
    """, [facility_id, current_user.property_id])

    if not facility:
        flash('ไม่พบสิ่งอำนวยความสะดวกนี้', 'danger')
        return redirect(url_for('facility.resident_facilities'))

    if request.method == 'POST':
        booking_date = request.form.get('booking_date')
        start_time   = request.form.get('start_time')

        if not booking_date or not start_time:
            flash('กรุณาเลือกวันและเวลา', 'danger')
            return redirect(request.url)

        # Calculate end time
        start_dt = datetime.strptime(start_time, '%H:%M')
        end_dt   = start_dt + timedelta(minutes=facility['slot_duration_mins'])
        end_time = end_dt.strftime('%H:%M')

        # ── Conflict check 1: Same unit already booked this slot ──
        unit_conflict = query_one("""
            SELECT idno FROM tblfacility_booking
            WHERE facility_id  = %s
              AND booking_date  = %s
              AND start_time    = %s
              AND unit_id       = %s
              AND status       != 'cancelled'
        """, [facility_id, booking_date, start_time, current_user.unit_id])

        if unit_conflict:
            flash('⚠️ สมาชิกในห้องของคุณได้จองสล็อตนี้แล้ว กรุณาเลือกเวลาอื่น', 'warning')
            return redirect(request.url)

        # ── Conflict check 2: Capacity check ──
        if facility['max_capacity']:
            booked_count = query_one("""
                SELECT COUNT(*) AS cnt FROM tblfacility_booking
                WHERE facility_id  = %s
                  AND booking_date  = %s
                  AND start_time    = %s
                  AND status       != 'cancelled'
            """, [facility_id, booking_date, start_time])['cnt']

            if booked_count >= facility['max_capacity']:
                flash('❌ สล็อตนี้เต็มแล้ว กรุณาเลือกเวลาอื่น', 'danger')
                return redirect(request.url)

        # ── Determine status ──
        status = 'pending' if facility['approval_required'] else 'confirmed'

        db  = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO tblfacility_booking
                (facility_id, property_id, unit_id, booked_by,
                 booking_date, start_time, end_time,
                 status, fee_amount, payment_method)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING idno
        """, [facility_id, current_user.property_id,
              current_user.unit_id, current_user.id,
              booking_date, start_time, end_time,
              status, facility['fee_amount'],
              facility['payment_method']])
        db.commit()

        if status == 'confirmed':
            flash(f'✅ จองสำเร็จ! {facility["name"]} วันที่ {booking_date} เวลา {start_time}-{end_time}', 'success')
        else:
            flash(f'⏳ ส่งคำขอจองแล้ว รอเจ้าหน้าที่อนุมัติภายใน 24 ชั่วโมง', 'success')

        return redirect(url_for('facility.my_bookings'))

    # GET — show booking form with available slots
    selected_date = request.args.get('date', date.today().isoformat())
    slots = get_time_slots(facility, selected_date)

    # Get bookings for selected date to show availability
    slot_bookings = query_all("""
        SELECT start_time, COUNT(*) AS cnt, 
               MAX(CASE WHEN unit_id = %s THEN 1 ELSE 0 END) AS unit_booked
        FROM tblfacility_booking
        WHERE facility_id  = %s
          AND booking_date  = %s
          AND status       != 'cancelled'
        GROUP BY start_time
    """, [current_user.unit_id, facility_id, selected_date])

    slot_status = {}
    for sb in slot_bookings:
        t = str(sb['start_time'])[:5]
        slot_status[t] = {
            'count':       sb['cnt'],
            'unit_booked': sb['unit_booked']
        }

    return render_template('facility/book.html',
        facility=facility,
        slots=slots,
        slot_status=slot_status,
        selected_date=selected_date,
        today=date.today().isoformat(),
        max_date=(date.today() + timedelta(days=30)).isoformat())


@facility_bp.route('/my-bookings')
@login_required
def my_bookings():
    """Resident views their own bookings."""
    if not current_user.is_resident:
        return redirect(url_for('facility.dashboard'))

    bookings = query_all("""
        SELECT b.idno, b.booking_date, b.start_time, b.end_time,
               b.status, b.fee_amount, b.fee_paid, b.payment_method,
               b.created_at,
               f.name AS facility_name, f.icon
        FROM tblfacility_booking b
        JOIN tblfacility f ON b.facility_id = f.idno
        WHERE b.unit_id = %s
          AND b.booking_date >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY b.booking_date DESC, b.start_time DESC
        LIMIT 20
    """, [current_user.unit_id])

    return render_template('facility/my_bookings.html', bookings=bookings)


@facility_bp.route('/cancel-my/<int:booking_id>', methods=['POST'])
@login_required
def cancel_my_booking(booking_id):
    """Resident cancels their own booking."""
    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblfacility_booking SET
            status       = 'cancelled',
            cancelled_by = %s,
            cancelled_at = NOW()
        WHERE idno = %s
          AND unit_id = %s
          AND status  != 'cancelled'
          AND booking_date >= CURRENT_DATE
    """, [current_user.id, booking_id, current_user.unit_id])
    db.commit()
    flash('ยกเลิกการจองแล้ว', 'success')
    return redirect(url_for('facility.my_bookings'))
