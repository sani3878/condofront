from flask import Flask, redirect, url_for
from .extensions import login_manager
from .helpers import close_db
from config import config


def create_app(env='default'):
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(config[env])

    # Default route
    @app.route("/")
    def home():
        return redirect(url_for("auth.login"))

    # Session config — same as your IJ-FLOW
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_TYPE'] = 'filesystem'

    # Extensions
    login_manager.init_app(app)

    # Teardown DB connection per request
    app.teardown_appcontext(close_db)

    # Register blueprints
    from .auth.routes import auth_bp
    from .parcel.routes import parcel_bp
    from .property.routes import property_bp
    from .report.routes import report_bp
    from .admin.routes import admin_bp

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
