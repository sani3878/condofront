from flask import Blueprint

report_bp = Blueprint('report', __name__, url_prefix='/report')

from . import routes  # noqa
