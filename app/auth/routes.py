from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from . import auth_bp
from ..models import User
from ..helpers import query_one, query_all, get_db


# Update get_next_page to use dashboard
# ── HELPER — must be defined before login route ──────────────
def get_next_page(user):
    """Smart redirect based on actual database state."""

    # Tier 1 — check property exists in DB (not user object)
    property = query_one("""
        SELECT idno FROM tblproperty
        WHERE customer_id = %s AND is_active = TRUE
        LIMIT 1
    """, [user.customer_id])

    if not property:
        return url_for('property.dashboard')

    # Tier 2 — check rooms exist
    room_count = query_one("""
        SELECT COUNT(*) as cnt 
        FROM tblroom 
        WHERE property_id = %s 
        AND is_active = TRUE
    """, [property['idno']])

    if not room_count or room_count['cnt'] == 0:
        return url_for('property.dashboard')

    return url_for('parcel.receive')




@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(get_next_page(current_user))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.get_by_email(email)

        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=False)
            next_page = request.args.get('next')
            return redirect(next_page or get_next_page(user))

        flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        customer_name = request.form.get('customer_name', '').strip()
        email         = request.form.get('email', '').strip().lower()
        password      = request.form.get('password', '')
        confirm       = request.form.get('confirm_password', '')
        fullname      = request.form.get('fullname', '').strip()
        mobile        = request.form.get('mobile', '').strip()
        package_id    = request.form.get('package_id')

        # ── Validation ──────────────────────────────────────────
        if not all([customer_name, email, password, fullname, package_id]):
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('auth.register'))

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.register'))

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('auth.register'))

        if query_one('SELECT idno FROM tbluser WHERE email = %s', [email]):
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))

        # ── Create records in one transaction ───────────────────
        db  = get_db()
        cur = db.cursor()

        try:
            # 1. Create customer (billing entity)
            cur.execute("""
                INSERT INTO tblcustomer
                    (customer_name, email, mobile, is_active)
                VALUES (%s, %s, %s, TRUE)
                RETURNING idno
            """, [customer_name, email, mobile or None])
            customer_id = cur.fetchone()['idno']

            # 2. Create user linked to customer
            #    property_id = NULL at signup (no property yet)
            #    role_id = 2 (Manager — owner of the account)
            cur.execute("""
                INSERT INTO tbluser
                    (customer_id, property_id, role_id,
                     email, password_hash, fullname, mobile, is_active)
                VALUES (%s, NULL, 2, %s, %s, %s, %s, TRUE)
                RETURNING idno
            """, [customer_id, email,
                  generate_password_hash(password),
                  fullname, mobile or None])

           
            # 3. Package stored at property setup step
            

            db.commit()
            flash('Registration successful! Please login to set up your property.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
            return redirect(url_for('auth.register'))

    packages = query_all("""
        SELECT idno, package_name, monthly_fee,
               max_room, max_user, max_parcel
        FROM tblpackage
        WHERE is_active = TRUE
        ORDER BY monthly_fee
    """)
    return render_template('auth/register.html', packages=packages)


@auth_bp.route('/forgot-password')
def forgot_password():
    return render_template('auth/forgot_password.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))





@auth_bp.route('/language/<lang>')
def set_language(lang):
    from flask import session
    if lang in ('th', 'en'):
        session['lang'] = lang
    # Go back to where user came from
    return redirect(request.referrer or url_for('parcel.receive'))
