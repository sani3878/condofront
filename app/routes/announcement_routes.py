from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ..blueprints import announcement_bp
from ..helpers import query_all, query_one, get_db
from ..mail import _send
from ..decorators import staff_required, resident_required


# ── JURISTIC / STAFF ROUTES ─────────────────────────────────

@announcement_bp.route('/')
@login_required
@staff_required
def list_announcements():
    if current_user.is_resident:
        return redirect(url_for('announcement.resident_view'))

    announcements = query_all("""
        SELECT a.idno, a.title, a.body, a.target,
               a.send_email, a.is_active, a.created_at, a.expires_at,
               u.fullname AS created_by_name,
               r.room_no, r.building,
               (SELECT COUNT(*) FROM tblannouncement_read ar
                WHERE ar.announcement_id = a.idno) AS read_count
        FROM tblannouncement a
        LEFT JOIN tbluser u ON a.created_by = u.idno
        LEFT JOIN tblroom r ON a.target_room_id = r.idno
        WHERE a.property_id = %s
        ORDER BY a.created_at DESC
        LIMIT 50
    """, [current_user.property_id])

    rooms = query_all("""
        SELECT idno, building, room_no FROM tblroom
        WHERE property_id = %s AND is_active = TRUE
        ORDER BY building, room_no
    """, [current_user.property_id])

    residents = query_all("""
        SELECT u.idno, u.fullname, u.email, r.room_no, r.building
        FROM tbluser u
        JOIN tblroom r ON u.unit_id = r.idno
        WHERE u.property_id = %s AND u.role_id = 4 AND u.is_active = TRUE
        ORDER BY r.building, r.room_no, u.fullname
    """, [current_user.property_id])

    return render_template('announcement/list.html',
        active_page='announcement',
        announcements=announcements,
        rooms=rooms,
        residents=residents)


@announcement_bp.route('/create', methods=['POST'])
@login_required
@staff_required
def create():
    if current_user.is_resident:
        return redirect(url_for('announcement.resident_view'))

    title          = request.form.get('title', '').strip()
    body           = request.form.get('body', '').strip()
    target         = request.form.get('target', 'all')
    target_user_id = request.form.get('target_user_id') or None
    send_email     = request.form.get('send_email') == 'true'
    expires_days   = request.form.get('expires_days') or None

    if not title or not body:
        flash('กรุณากรอกหัวข้อและเนื้อหา', 'danger')
        return redirect(url_for('announcement.list_announcements'))

    expires_at = None
    if expires_days:
        expires_at = datetime.now() + timedelta(days=int(expires_days))

    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO tblannouncement
            (property_id, created_by, title, body,
             target, target_user_id, send_email,
             is_active, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s)
        RETURNING idno
    """, [current_user.property_id, current_user.id,
          title, body, target, target_user_id,
          send_email, expires_at])
    ann_id = cur.fetchone()['idno']
    db.commit()

    # Send email if requested and target is specific resident
    if send_email and target_user_id:
        resident = query_one("""
            SELECT u.fullname, u.email, r.room_no, r.building,
                   p.property_name
            FROM tbluser u
            LEFT JOIN tblroom r ON u.unit_id = r.idno
            LEFT JOIN tblproperty p ON u.property_id = p.idno
            WHERE u.idno = %s
        """, [target_user_id])

        if resident and resident['email']:
            try:
                _send(
                    resident['email'],
                    f'📢 {title} — {resident["property_name"]}',
                    f"""สวัสดีคุณ {resident['fullname']},

{title}

{body}

ห้อง: {resident['building'] or ''}{resident['room_no']}
โครงการ: {resident['property_name']}

ทีมงานนิติบุคคล
"""
                )
                flash(f'ส่งประกาศและอีเมลถึง {resident["fullname"]} สำเร็จ', 'success')
            except Exception:
                flash('ส่งประกาศสำเร็จ แต่ส่งอีเมลไม่ได้', 'warning')
        return redirect(url_for('announcement.list_announcements'))

    flash('สร้างประกาศสำเร็จ', 'success')
    return redirect(url_for('announcement.list_announcements'))


@announcement_bp.route('/delete/<int:ann_id>', methods=['POST'])
@login_required
@staff_required
def delete(ann_id):
    db  = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE tblannouncement SET is_active = FALSE
        WHERE idno = %s AND property_id = %s
    """, [ann_id, current_user.property_id])
    db.commit()
    flash('ลบประกาศแล้ว', 'success')
    return redirect(url_for('announcement.list_announcements'))


# ── RESIDENT ROUTES ─────────────────────────────────────────

@announcement_bp.route('/my')
@login_required
@resident_required
def resident_view():
    if not current_user.is_resident:
        return redirect(url_for('announcement.list_announcements'))

    announcements = query_all("""
        SELECT a.idno, a.title, a.body, a.created_at,
               a.target, a.target_user_id,
               EXISTS(
                   SELECT 1 FROM tblannouncement_read ar
                   WHERE ar.announcement_id = a.idno
                   AND ar.user_id = %s
               ) AS is_read
        FROM tblannouncement a
        WHERE a.property_id = %s
          AND a.is_active = TRUE
          AND (a.expires_at IS NULL OR a.expires_at > NOW())
          AND (
              a.target = 'all'
              OR a.target_user_id = %s
          )
        ORDER BY a.created_at DESC
        LIMIT 30
    """, [current_user.id, current_user.property_id, current_user.id])

    return render_template('announcement/resident.html',
        announcements=announcements)


@announcement_bp.route('/read/<int:ann_id>', methods=['POST'])
@login_required
@resident_required
def mark_read(ann_id):
    db  = get_db()
    cur = db.cursor()
    try:
        cur.execute("""
            INSERT INTO tblannouncement_read (announcement_id, user_id)
            VALUES (%s, %s) ON CONFLICT DO NOTHING
        """, [ann_id, current_user.id])
        db.commit()
    except Exception:
        pass
    return jsonify({'ok': True})


# ── UNREAD COUNT (for badge on home) ────────────────────────
def get_unread_count(user_id, property_id, is_resident=False):
    """Returns unread announcement count for badges."""
    if is_resident:
        result = query_one("""
            SELECT COUNT(*) AS cnt FROM tblannouncement a
            WHERE a.property_id = %s
              AND a.is_active = TRUE
              AND (a.expires_at IS NULL OR a.expires_at > NOW())
              AND (a.target = 'all' OR a.target_user_id = %s)
              AND NOT EXISTS (
                  SELECT 1 FROM tblannouncement_read ar
                  WHERE ar.announcement_id = a.idno
                  AND ar.user_id = %s
              )
        """, [property_id, user_id, user_id])
    else:
        result = query_one("""
            SELECT COUNT(*) AS cnt FROM tblannouncement a
            WHERE a.property_id = %s
              AND a.is_active = TRUE
              AND a.target = 'all'
              AND (a.expires_at IS NULL OR a.expires_at > NOW())
              AND NOT EXISTS (
                  SELECT 1 FROM tblannouncement_read ar
                  WHERE ar.announcement_id = a.idno
                  AND ar.user_id = %s
              )
        """, [property_id, user_id])
    return result['cnt'] if result else 0
