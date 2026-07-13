"""
Role-based access decorators for CondoFront.
Add these to any route that needs role protection.
"""
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


def staff_required(f):
    """Only staff (Manager, Reception, Security) can access."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.is_resident:
            flash('ไม่มีสิทธิ์เข้าถึงหน้านี้', 'danger')
            return redirect(url_for('resident.home'))
        if current_user.is_superadmin:
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated


def resident_required(f):
    """Only residents can access."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_resident:
            if current_user.is_superadmin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Only SuperAdmin can access."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.is_superadmin:
            flash('ไม่มีสิทธิ์เข้าถึงหน้านี้', 'danger')
            if current_user.is_resident:
                return redirect(url_for('resident.home'))
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated


def manager_required(f):
    """Only Manager (role_id=1) can access — not Reception/Security."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role_id != 1:
            flash('เฉพาะผู้จัดการเท่านั้น', 'danger')
            if current_user.is_resident:
                return redirect(url_for('resident.home'))
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated
