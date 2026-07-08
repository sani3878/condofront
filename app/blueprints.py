from flask import Blueprint

auth_bp     = Blueprint('auth',     __name__, url_prefix='/auth')
parcel_bp   = Blueprint('parcel',   __name__, url_prefix='/parcel')
property_bp = Blueprint('property', __name__, url_prefix='/property')
report_bp   = Blueprint('report',   __name__, url_prefix='/report')
main_bp     = Blueprint('main',     __name__)
resident_bp = Blueprint('resident', __name__, url_prefix='/resident')
visitor_bp  = Blueprint('visitor',  __name__, url_prefix='/visitor')
admin_bp    = Blueprint('admin',    __name__, url_prefix='/admin')
service_bp  = Blueprint('service',  __name__, url_prefix='/service')
facility_bp = Blueprint('facility', __name__, url_prefix='/facility')
