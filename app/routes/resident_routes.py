from flask import render_template, abort
from flask_login import login_required, current_user
from ..blueprints import resident_bp
from ..helpers import query_all, query_one


def resident_required(f):
    """Decorator to ensure only residents can access resident pages."""
    from functools import wraps
    from flask import redirect, url_for, flash
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_resident:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@resident_bp.route('/')
@resident_bp.route('/home')
@login_required
@resident_required
def home():
    # My unit info
    unit = query_one("""
        SELECT r.*, p.property_name
        FROM tblroom r
        JOIN tblproperty p ON r.property_id = p.idno
        WHERE r.idno = %s
    """, [current_user.unit_id]) if current_user.unit_id else None

    # Other members in the same unit
    unit_members = query_all("""
        SELECT fullname, mobile
        FROM tbluser
        WHERE unit_id = %s
          AND idno != %s
          AND is_active = TRUE
          AND role_id = 4
    """, [current_user.unit_id, current_user.id]) if current_user.unit_id else []

    # Waiting parcels count for unit card badge
    waiting = query_one("""
        SELECT COUNT(*) AS cnt FROM tblparcel
        WHERE room_id = %s AND status_id = 0 AND deleted_at IS NULL
    """, [current_user.unit_id])['cnt'] if current_user.unit_id else 0

    # Pending visitors pre-registered by this resident
    pending_visitors = query_one("""
        SELECT COUNT(*) AS cnt FROM tblvisitor
        WHERE registered_by = %s AND status = 'pending'
    """, [current_user.id])['cnt'] if current_user.id else 0

    # Unread announcements count
    unread_ann = query_one("""
        SELECT COUNT(*) AS cnt FROM tblannouncement a
        WHERE a.property_id = %s
          AND a.is_active = TRUE
          AND (a.expires_at IS NULL OR a.expires_at > NOW())
          AND (a.target = 'all' OR a.target_user_id = %s)
          AND NOT EXISTS (
              SELECT 1 FROM tblannouncement_read ar
              WHERE ar.announcement_id = a.idno AND ar.user_id = %s
          )
    """, [current_user.property_id, current_user.id, current_user.id])
    unread_ann = unread_ann['cnt'] if unread_ann else 0

    return render_template('resident/home.html',
        unit=unit,
        unit_members=unit_members,
        waiting=waiting,
        pending_visitors=pending_visitors,
        unread_ann=unread_ann)


@resident_bp.route('/unit')
@login_required
@resident_required
def unit():
    unit = query_one("""
        SELECT r.*, p.property_name
        FROM tblroom r
        JOIN tblproperty p ON r.property_id = p.idno
        WHERE r.idno = %s
    """, [current_user.unit_id]) if current_user.unit_id else None

    unit_members = query_all("""
        SELECT fullname, mobile
        FROM tbluser
        WHERE unit_id = %s
          AND idno != %s
          AND is_active = TRUE
          AND role_id = 4
    """, [current_user.unit_id, current_user.id]) if current_user.unit_id else []

    return render_template('resident/unit.html',
        unit=unit,
        unit_members=unit_members)


@resident_bp.route('/parcels')
@login_required
@resident_required
def parcels():
    parcels = query_all("""
        SELECT p.idno, p.tracking_no, p.received_at, p.parcel_type,
               p.status_id, p.note,
               c.courier_name,
               s.status_name
        FROM tblparcel p
        JOIN tblstatus s    ON p.status_id = s.idno
        LEFT JOIN tblcourier c ON p.courier_id = c.idno
        WHERE p.room_id = %s
          AND p.deleted_at IS NULL
        ORDER BY p.received_at DESC
        LIMIT 50
    """, [current_user.unit_id]) if current_user.unit_id else []

    waiting = sum(1 for p in parcels if p['status_id'] == 0)

    return render_template('resident/parcels.html',
        parcels=parcels,
        waiting=waiting)


@resident_bp.route('/parcel-qr/<int:parcel_id>')
@login_required
@resident_required
def parcel_qr(parcel_id):
    """Show QR code for resident to pickup their parcel."""
    parcel = query_one("""
        SELECT p.*, r.room_no, r.building,
               c.courier_name, pr.property_name
        FROM tblparcel p
        JOIN tblroom r ON p.room_id = r.idno
        JOIN tblproperty pr ON p.property_id = pr.idno
        LEFT JOIN tblcourier c ON p.courier_id = c.idno
        WHERE p.idno = %s
          AND p.room_id = %s
          AND p.status_id = 0
    """, [parcel_id, current_user.unit_id])

    if not parcel:
        flash('ไม่พบพัสดุ หรือรับไปแล้ว', 'warning')
        return redirect(url_for('resident.parcels'))

    return render_template('resident/parcel_qr.html', parcel=parcel)
