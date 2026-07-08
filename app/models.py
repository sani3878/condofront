from flask_login import UserMixin
from .helpers import query_one

class User(UserMixin):
    def __init__(self, row):
        self.id            = row['idno']
        self.customer_id   = row['customer_id']
        self.property_id   = row['property_id']
        self.role_id       = row['role_id']
        self.role_name     = row['role_name']
        self.email         = row['email']
        self.fullname      = row['fullname']
        self.mobile        = row['mobile']
        self.password_hash = row['password_hash']
        self.email_verified = row.get('email_verified', True)
        self.unit_id       = row.get('unit_id')
        self._is_active    = row['is_active']

    @property
    def is_active(self):
        return self._is_active

    @property
    def is_superadmin(self):
        return self.role_id == 5

    @property
    def is_resident(self):
        return self.role_id == 4

    @property
    def is_staff(self):
        return self.role_id in (1, 2, 3)

    def get_id(self):
        return str(self.id)

    @staticmethod
    def get_by_id(user_id):
        row = query_one("""
            SELECT u.*, r.role_name
            FROM tbluser u
            JOIN tblrole r ON u.role_id = r.idno
            WHERE u.idno = %s AND u.is_active = TRUE
        """, [user_id])
        return User(row) if row else None

    @staticmethod
    def get_by_email(email):
        row = query_one("""
            SELECT u.*, r.role_name
            FROM tbluser u
            JOIN tblrole r ON u.role_id = r.idno
            WHERE u.email = %s AND u.is_active = TRUE
        """, [email])
        return User(row) if row else None