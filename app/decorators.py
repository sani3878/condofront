from functools import wraps
from flask import abort
from flask_login import current_user

def roles_required(*roles):
    """Restrict route to specific role names e.g. @roles_required('Admin','Manager')"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if current_user.role_name not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator

def admin_only(f):
    """Shortcut — CondoFront super admin only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_superadmin:
            abort(403)
        return f(*args, **kwargs)
    return decorated
