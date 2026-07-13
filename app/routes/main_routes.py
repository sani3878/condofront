from flask import render_template
from flask_login import login_required, current_user
from ..blueprints import main_bp
from ..helpers import query_one
from ..decorators import staff_required


@main_bp.route('/')
@login_required
@staff_required
def home():
    # Quick stats for the home screen
    waiting = 0
    overdue = 0

    if current_user.property_id:
        waiting = query_one("""
            SELECT COUNT(*) AS cnt FROM tblparcel
            WHERE property_id = %s AND status_id = 0
            AND deleted_at IS NULL
        """, [current_user.property_id])['cnt']

        overdue = query_one("""
            SELECT COUNT(*) AS cnt FROM tblparcel
            WHERE property_id = %s AND status_id = 0
            AND received_at < NOW() - INTERVAL '3 days'
            AND deleted_at IS NULL
        """, [current_user.property_id])['cnt']

    return render_template('main/home.html',
        active_page='home',
        waiting=waiting,
        overdue=overdue)
