from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..blueprints import service_bp
from ..helpers import query_one, query_all, get_db

# ── STATUS CONFIG ────────────────────────────────────────────
STATUSES = [
    ('open',         '📬 เปิด',          '#f59e0b', 'open'),
    ('acknowledged', '👀 รับทราบ',        '#3b82f6', 'acknowledged'),
    ('scheduled',    '📅 นัดหมาย',        '#8b5cf6', 'scheduled'),
    ('in_progress',  '🔧 กำลังดำเนินการ', '#ff7a00', 'in_progress'),
    ('done',         '✅ เสร็จแล้ว',      '#22c55e', 'done'),
    ('closed',       '🔒 ปิด',            '#94a3b8', 'closed'),
]

STATUS_NEXT = {
    'open':         'acknowledged',
    'acknowledged': 'scheduled',
    'scheduled':    'in_progress',
    'in_progress':  'done',
    'done':         'closed',
}

STATUS_LABELS = {s[0]: s[1] for s in STATUSES}


def get_categories(property_id):
    if not property_id:
        return []

    cats = query_all("""
        SELECT * FROM tblservice_category
        WHERE property_id = %s AND is_active = TRUE
        ORDER BY name
    """, [property_id])

    # Auto-create defaults if none exist
    if not cats:
        defaults = [
            ('🔧', 'ซ่อมแซม / Repair'),
            ('🧹', 'ทำความสะอาด / Cleaning'),
            ('⚡', 'ระบบไฟฟ้า / Electrical'),
            ('💧', 'ระบบประปา / Plumbing'),
            ('🔑', 'กุญแจ / Access Card'),
            ('📦', 'ย้ายของ / Moving'),
            ('🔔', 'อื่นๆ / Other'),
        ]
        db  = get_db()
        cur = db.cursor()
        for icon, name in defaults:
            cur.execute("""
                INSERT INTO tblservice_category (property_id, icon, name)
                VALUES (%s, %s, %s)
            """, [property_id, icon, name])
        db.commit()
        cats = query_all("""
            SELECT * FROM tblservice_category
            WHERE property_id = %s AND is_active = TRUE
            ORDER BY name
        """, [property_id])
    return cats


# ── STAFF ROUTES ────────────────────────────────────────────

@service_bp.route('/')
@login_required
def list_requests():
    if current_user.is_resident:
        return redirect(url_for('service.my_requests'))

    status_filter = request.args.get('status', 'open')
    search        = request.args.get('q', '').strip()

    sql = """
        SELECT sr.idno, sr.title, sr.description, sr.status,
               sr.fee, sr.fee_paid, sr.created_at, sr.scheduled_at,
               sr.note,
               r.room_no, r.building,
               c.name AS category_name, c.icon AS category_icon,
               u.fullname AS submitted_by_name,
               a.fullname AS assigned_to_name
        FROM tblservice_request sr
        LEFT JOIN tblroom r ON sr.room_id = r.idno
        LEFT JOIN tblservice_category c ON sr.category_id = c.idno
        LEFT JOIN tbluser u ON sr.submitted_by = u.idno
        LEFT JOIN tbluser a ON sr.assigned_to = a.idno
        WHERE sr.property_id = %s
    """
    params = [current_user.property_id]

    if search:
        sql += " AND (sr.title ILIKE %s OR r.room_no ILIKE %s)"
        params += [f'%{search}%', f'%{search}%']
    elif status_filter != 'all':
        sql += " AND sr.status = %s"
        params.append(status_filter)

    sql += " ORDER BY sr.created_at DESC LIMIT 100"
    requests_list = query_all(sql, params)

    # Counts per status
    counts = {}
    for s, _, _, _ in STATUSES:
        row = query_one("""
            SELECT COUNT(*) AS cnt FROM tblservice_request
            WHERE property_id = %s AND status = %s
        """, [current_user.property_id, s])
        counts[s] = row['cnt'] if row else 0

    categories = get_categories(current_user.property_id)
    staff_list = query_all("""
        SELECT idno, fullname FROM tbluser
        WHERE property_id = %s AND is_active = TRUE
        AND role_id IN (1, 2, 3)
        ORDER BY fullname
    """, [current_user.property_id])

    rooms = query_all("""
        SELECT idno, building, room_no FROM tblroom
        WHERE property_id = %s AND is_active = TRUE
        ORDER BY building, room_no
    """, [current_user.property_id])

    return render_template('service/list.html',
        active_page='service',
        requests=requests_list,
        counts=counts,
        statuses=STATUSES,
        status_filter=status_filter,
        status_next=STATUS_NEXT,
        status_labels=STATUS_LABELS,
        categories=categories,
        staff_list=staff_list,
        rooms=rooms,
        search=search)


@service_bp.route('/create', methods=['POST'])
@login_required
def create():
    title       = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip() or None
    category_id = request.form.get('category_id') or None
    room_id     = request.form.get('room_id') or None
    fee         = request.form.get('fee') or None

    if not title:
        flash('กรุณากรอกหัวข้อ', 'danger')
        return redirect(url_for('service.list_requests'))

    # Residents use their own unit
    if current_user.is_resident:
        room_id = current_user.unit_id

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO tblservice_request
            (property_id, room_id, category_id, submitted_by,
             title, description, fee, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'open', NOW())
        RETURNING idno
    """, [current_user.property_id, room_id, category_id,
          current_user.id, title, description, fee])
    db.commit()

    flash(f'บันทึกคำร้องสำเร็จ: {title}', 'success')
    if current_user.is_resident:
        return redirect(url_for('service.my_requests'))
    return redirect(url_for('service.list_requests'))


@service_bp.route('/update/<int:req_id>', methods=['POST'])
@login_required
def update(req_id):
    new_status  = request.form.get('status')
    note        = request.form.get('note', '').strip() or None
    fee         = request.form.get('fee') or None
    fee_paid    = request.form.get('fee_paid') == 'true'
    assigned_to = request.form.get('assigned_to') or None
    scheduled   = request.form.get('scheduled_at') or None

    db  = get_db()
    cur = db.cursor()

    closed_at = 'NOW()' if new_status == 'closed' else 'NULL'
    closed_by = current_user.id if new_status == 'closed' else None

    cur.execute(f"""
        UPDATE tblservice_request SET
            status      = %s,
            note        = COALESCE(%s, note),
            fee         = COALESCE(%s::numeric, fee),
            fee_paid    = %s,
            assigned_to = COALESCE(%s::bigint, assigned_to),
            scheduled_at = COALESCE(%s::timestamp, scheduled_at),
            updated_at  = NOW(),
            closed_at   = {closed_at},
            closed_by   = %s
        WHERE idno = %s AND property_id = %s
    """, [new_status, note, fee, fee_paid,
          assigned_to, scheduled, closed_by,
          req_id, current_user.property_id])
    db.commit()

    flash(f'อัปเดตสถานะเป็น {STATUS_LABELS.get(new_status, new_status)} แล้ว', 'success')
    return redirect(url_for('service.list_requests',
                            status=request.form.get('from_status', 'open')))


# ── RESIDENT ROUTES ─────────────────────────────────────────

@service_bp.route('/my')
@login_required
def my_requests():
    if not current_user.is_resident:
        return redirect(url_for('service.list_requests'))

    requests_list = query_all("""
        SELECT sr.idno, sr.title, sr.description, sr.status,
               sr.fee, sr.fee_paid, sr.created_at, sr.scheduled_at,
               c.name AS category_name, c.icon AS category_icon
        FROM tblservice_request sr
        LEFT JOIN tblservice_category c ON sr.category_id = c.idno
        WHERE sr.submitted_by = %s
        ORDER BY sr.created_at DESC
        LIMIT 20
    """, [current_user.id])

    categories = get_categories(current_user.property_id) if current_user.property_id else []

    return render_template('service/my_requests.html',
        requests=requests_list,
        categories=categories,
        statuses=STATUSES,
        status_labels=STATUS_LABELS)


# ── CATEGORY MANAGEMENT ──────────────────────────────────────

@service_bp.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    if current_user.is_resident:
        return redirect(url_for('resident.home'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        icon = request.form.get('icon', '🔧').strip()
        fee  = request.form.get('default_fee') or None

        if name:
            db  = get_db()
            cur = db.cursor()
            cur.execute("""
                INSERT INTO tblservice_category
                    (property_id, name, icon, default_fee)
                VALUES (%s, %s, %s, %s)
            """, [current_user.property_id, name, icon, fee])
            db.commit()
            flash(f'เพิ่มหมวดหมู่ {name} แล้ว', 'success')

        return redirect(url_for('service.categories'))

    cats = get_categories(current_user.property_id)
    return render_template('service/categories.html',
        active_page='service',
        categories=cats)


@service_bp.route('/categories/delete/<int:cat_id>', methods=['POST'])
@login_required
def delete_category(cat_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblservice_category SET is_active = FALSE
        WHERE idno = %s AND property_id = %s
    """, [cat_id, current_user.property_id])
    db.commit()
    flash('ลบหมวดหมู่แล้ว', 'success')
    return redirect(url_for('service.categories'))
