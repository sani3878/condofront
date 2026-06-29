from flask import Blueprint

parcel_bp = Blueprint('parcel', __name__, url_prefix='/parcel')

from . import routes  # noqa
