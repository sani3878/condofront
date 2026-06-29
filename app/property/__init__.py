from flask import Blueprint

property_bp = Blueprint('property', __name__, url_prefix='/property')

from . import routes  # noqa
