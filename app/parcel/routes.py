from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from . import parcel_bp
from ..helpers import query_one, query_all, get_db

@parcel_bp.route('/')
@parcel_bp.route('/receive', methods=['GET', 'POST'])
@login_required
def receive():
    if request.method == 'POST':
        room_id    = request.form.get('room_id')
        courier_id = request.form.get('courier_id')
        tracking   = request.form.get('tracking_no', '').strip()
        note       = request.form.get('note', '').strip()

        if not room_id:
            flash('กรุณาเลือกห้อง', 'danger')
            return redirect(url_for('parcel.receive'))

        db  = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO tblparcel
                (property_id, room_id, courier_id, tracking_no,
                 note, received_by, status_id)
            VALUES (%s, %s, %s, %s, %s, %s, 0)
            RETURNING idno
        """, [current_user.property_id,
              room_id,
              courier_id or None,
              tracking or None,
              note or None,
              current_user.id])
        parcel_id = cur.fetchone()['idno']
        db.commit()

        return redirect(url_for('parcel.print_label', parcel_id=parcel_id))

    # Stats
    today_count = query_one("""
        SELECT COUNT(*) AS cnt FROM tblparcel
        WHERE property_id = %s
          AND DATE(received_at) = CURRENT_DATE
          AND deleted_at IS NULL
    """, [current_user.property_id])['cnt']

    waiting_count = query_one("""
        SELECT COUNT(*) AS cnt FROM tblparcel
        WHERE property_id = %s
          AND status_id = 0
          AND deleted_at IS NULL
    """, [current_user.property_id])['cnt']

    recent = query_all("""
        SELECT p.received_at, r.room_no, r.building,
               c.courier_name
        FROM tblparcel p
        JOIN tblroom r ON p.room_id = r.idno
        LEFT JOIN tblcourier c ON p.courier_id = c.idno
        WHERE p.property_id = %s
          AND DATE(p.received_at) = CURRENT_DATE
          AND p.deleted_at IS NULL
        ORDER BY p.received_at DESC
        LIMIT 8
    """, [current_user.property_id])

    couriers = query_all("""
        SELECT idno, courier_name FROM tblcourier
        WHERE is_active = TRUE ORDER BY courier_name
    """)

    return render_template('parcel/receive.html',
        active_page='receive',
                           couriers=couriers,
                           today_count=today_count,
                           waiting_count=waiting_count,
                           recent=recent)


@parcel_bp.route('/label/<int:parcel_id>')
@login_required
def print_label(parcel_id):
    parcel = query_one("""
        SELECT p.*, r.room_no, r.building, r.floor,
               c.courier_name, pr.property_name
        FROM tblparcel p
        JOIN tblroom r      ON p.room_id = r.idno
        JOIN tblproperty pr ON p.property_id = pr.idno
        LEFT JOIN tblcourier c ON p.courier_id = c.idno
        WHERE p.idno = %s AND p.property_id = %s
    """, [parcel_id, current_user.property_id])

    if not parcel:
        flash('ไม่พบข้อมูลพัสดุ', 'danger')
        return redirect(url_for('parcel.receive'))

    return render_template('parcel/label.html', parcel=parcel)


@parcel_bp.route('/list')
@login_required
def list_parcels():
    status_id = request.args.get('status', 0, type=int)
    search    = request.args.get('q', '').strip()

    # Build query
    sql = """
        SELECT p.idno, p.tracking_no, p.received_at,
               p.note, p.status_id,
               r.room_no, r.building,
               c.courier_name,
               s.status_name
        FROM tblparcel p
        JOIN tblroom r      ON p.room_id = r.idno
        JOIN tblstatus s    ON p.status_id = s.idno
        LEFT JOIN tblcourier c ON p.courier_id = c.idno
        WHERE p.property_id = %s
          AND p.deleted_at IS NULL
    """
    params = [current_user.property_id]

    if search:
        sql += """
            AND (r.room_no ILIKE %s
              OR (r.building || r.room_no) ILIKE %s
              OR p.tracking_no ILIKE %s)
        """
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    elif status_id == 99:
        pass  # show all
    else:
        sql += " AND p.status_id = %s"
        params.append(status_id)

    sql += " ORDER BY p.received_at DESC LIMIT 200"

    parcels  = query_all(sql, params)
    statuses = query_all(
        "SELECT * FROM tblstatus WHERE is_active=TRUE ORDER BY idno")

    # Counts for summary bar
    counts = {}
    counts['waiting'] = query_one("""
        SELECT COUNT(*) as cnt FROM tblparcel
        WHERE property_id = %s AND status_id = 0
          AND deleted_at IS NULL
    """, [current_user.property_id])['cnt']

    counts['today'] = query_one("""
        SELECT COUNT(*) as cnt FROM tblparcel
        WHERE property_id = %s
          AND DATE(received_at) = CURRENT_DATE
          AND deleted_at IS NULL
    """, [current_user.property_id])['cnt']

    counts['overdue'] = query_one("""
        SELECT COUNT(*) as cnt FROM tblparcel
        WHERE property_id = %s
          AND status_id = 0
          AND received_at < NOW() - INTERVAL '3 days'
          AND deleted_at IS NULL
    """, [current_user.property_id])['cnt']

    return render_template('parcel/list.html',
        active_page='list',
                           parcels=parcels,
                           statuses=statuses,
                           current_status=status_id,
                           search=search,
                           counts=counts,
                           now=datetime.now())


@parcel_bp.route('/pickup/<int:parcel_id>', methods=['GET', 'POST'])
@login_required
def pickup(parcel_id):
    parcel = query_one("""
        SELECT p.*, r.room_no, r.building
        FROM tblparcel p
        JOIN tblroom r ON p.room_id = r.idno
        WHERE p.idno = %s
          AND p.property_id = %s
          AND p.status_id = 0
    """, [parcel_id, current_user.property_id])

    if not parcel:
        flash('ไม่พบพัสดุ หรือรับไปแล้ว', 'warning')
        return redirect(url_for('parcel.list_parcels'))

    if request.method == 'POST':
        pickup_note = request.form.get('pickup_note', '').strip()

        db  = get_db()
        cur = db.cursor()

        signature_data = request.form.get('signature_data', '')
        cur.execute("""
            INSERT INTO tblpickup
            (property_id, room_id, signature_path,pickup_note, handled_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING idno
        """, [current_user.property_id,
            parcel['room_id'],
            signature_data or None,
            pickup_note or None,
            current_user.id])        
        pickup_id = cur.fetchone()['idno']

        cur.execute("""
            UPDATE tblparcel
            SET status_id  = 1,
                pickup_id  = %s,
                updated_by = %s,
                updated_at = NOW()
            WHERE idno = %s
        """, [pickup_id, current_user.id, parcel_id])

        db.commit()
        flash(f'บันทึกการรับพัสดุห้อง {parcel["building"] or ""}{parcel["room_no"]} สำเร็จ!', 'success')
        return redirect(url_for('parcel.list_parcels'))

    return render_template('parcel/pickup.html', 
                       parcel=parcel,
                       now=datetime.now())


@parcel_bp.route('/api/rooms')
@login_required
def api_rooms():
    q    = request.args.get('q', '').strip()
    rows = query_all("""
        SELECT idno, room_no, building, floor
        FROM tblroom
        WHERE property_id = %s
          AND is_active = TRUE
          AND (room_no ILIKE %s
            OR (building || room_no) ILIKE %s)
        ORDER BY building, room_no
        LIMIT 20
    """, [current_user.property_id, f'%{q}%', f'%{q}%'])
    return jsonify([dict(r) for r in rows])
