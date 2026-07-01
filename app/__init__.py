from flask import Flask
from .extensions import login_manager
from .helpers import close_db
from config import config

def create_app(env='default'):
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(config[env])

    # Session config — same as your IJ-FLOW
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_TYPE'] = 'filesystem'

    # Extensions
    login_manager.init_app(app)

    # Teardown DB connection per request
    app.teardown_appcontext(close_db)

    # Inject current subscription plan into every template
    from flask_login import current_user
    from .helpers import query_one

    @app.context_processor
    def inject_plan():
        plan_name = None
        if current_user.is_authenticated and current_user.property_id:
            try:
                sub = query_one("""
                    SELECT pkg.package_name
                    FROM tblsubscription s
                    JOIN tblpackage pkg ON s.package_id = pkg.idno
                    WHERE s.property_id = %s AND s.is_active = TRUE
                    ORDER BY s.idno DESC LIMIT 1
                """, [current_user.property_id])
                if sub:
                    plan_name = sub['package_name']
            except Exception:
                pass
        return {'current_plan': plan_name}

    # Register blueprints
    from .auth.routes     import auth_bp
    from .parcel.routes   import parcel_bp
    from .property.routes import property_bp
    from .report.routes   import report_bp
    from .admin.routes    import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(parcel_bp)
    app.register_blueprint(property_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(admin_bp)

    # User loader for Flask-Login
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(user_id)

    return app
