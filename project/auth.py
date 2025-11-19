from flask import Blueprint, request, redirect, url_for, render_template, flash, session, current_app
from flask_login import login_required, logout_user, login_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
import re

from . import db
from .models import User, Role, Department, Major

auth = Blueprint('auth', __name__)

# --------------------------
# Regex patterns
# --------------------------
NSHE_RE = re.compile(r'^\d{10}$')
STUDENT_EMAIL_RE = re.compile(r'^(\d{10})@student\.csn\.edu$', re.I)
FACULTY_EMAIL_RE = re.compile(r'^[a-z]+\.\d{6,10}@csn\.edu$', re.I)

def _clean(s: str) -> str:
    return (s or '').strip()

def _email_lower(s: str) -> str:
    return (s or '').strip().lower()

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    roles = ['Student', 'Faculty']
    departments = Department.query.all()
    majors = Major.query.all()

    def render_signup_page(role_lower=None):
        return render_template(
            'signup.html',
            roles=roles,
            departments=departments,
            majors=majors,
            selected_role=role_lower
        )

    if request.method == 'GET':
        return render_signup_page()

    role_raw = _clean(request.form.get('role'))
    role_lower = role_raw.lower() if role_raw else ''
    first_name = _clean(request.form.get('first_name'))
    last_name = _clean(request.form.get('last_name'))
    phone = _clean(request.form.get('phone'))
    email_raw = _email_lower(request.form.get('email'))
    nshe = _clean(request.form.get('nshe'))
    major_name = _clean(request.form.get('major'))
    department_id = _clean(request.form.get('department_id'))
    employee_id = _clean(request.form.get('employee_id'))

    if role_lower not in ('student', 'faculty'):
        flash('Please choose Student or Faculty.', 'signup')
        return render_signup_page(role_lower)

    if not first_name or not last_name or not phone:
        flash('First name, last name, and phone are required.', 'signup')
        return render_signup_page(role_lower)

    if role_lower == 'student':
        m = STUDENT_EMAIL_RE.match(email_raw)
        if not m:
            flash('Student email must be NSHEID@student.csn.edu.', 'signup')
            return render_signup_page(role_lower)

        email_nshe = m.group(1)
        if not NSHE_RE.match(nshe):
            flash('NSHE must be exactly 10 digits.', 'signup')
            return render_signup_page(role_lower)

        if nshe != email_nshe:
            flash('NSHE must match the email prefix (before @).', 'signup')
            return render_signup_page(role_lower)

        if not major_name:
            flash('Please choose your major.', 'signup')
            return render_signup_page(role_lower)

        password_plain = nshe

    else:  # Faculty
        if not employee_id or not re.match(r'^\d{6,10}$', employee_id):
            flash('Employee ID must be 6–10 digits.', 'signup')
            return render_signup_page(role_lower)

        canonical_email = f"{first_name.strip().lower()}.{employee_id}@csn.edu"
        if not FACULTY_EMAIL_RE.match(canonical_email):
            flash('Faculty email must be firstname.employeeID@csn.edu.', 'signup')
            return render_signup_page(role_lower)

        email_raw = canonical_email
        if not department_id:
            flash('Department is required.', 'signup')
            return render_signup_page(role_lower)

        password_plain = employee_id

    role_obj = Role.query.filter_by(name=role_lower.title()).first()
    if not role_obj:
        flash('Role not configured; contact admin.', 'signup')
        return render_signup_page(role_lower)

    dept = None
    major = None

    if role_lower == 'student':
        major = Major.query.filter_by(name=major_name).first()
        if not major:
            flash('Selected major not found.', 'signup')
            return render_signup_page(role_lower)
        dept = Department.query.get(major.department_id)
    else:
        try:
            dept_id_int = int(department_id)
        except (TypeError, ValueError):
            flash('Invalid department selection.', 'signup')
            return render_signup_page(role_lower)
        dept = Department.query.get(dept_id_int)

    if not dept:
        flash('Invalid department selected.', 'signup')
        return render_signup_page(role_lower)

    email_lc = _email_lower(email_raw)

    existing_user = None
    if role_lower == 'student' and nshe:
        existing_user = User.query.filter(
            or_(User.nshe_id == nshe, User.email == email_lc)
        ).first()
    elif role_lower == 'faculty' and employee_id:
        existing_user = User.query.filter(
            or_(User.employee_id == employee_id, User.email == email_lc)
        ).first()
    else:
        existing_user = User.query.filter_by(email=email_lc).first()

    if existing_user:
        if role_lower == 'student' and existing_user.nshe_id == nshe:
            flash('This NSHE ID is already registered. Please try a different NSHE ID or log in instead.', 'signup')
        elif role_lower == 'faculty' and existing_user.employee_id == employee_id:
            flash('This Employee ID is already registered. Please try a different Employee ID or log in instead.', 'signup')
        else:
            flash('This email is already registered. Please try a different email or log in instead.', 'signup')
        return render_signup_page(role_lower)

    full_name = f"{first_name} {last_name}".strip()
    password_hash = generate_password_hash(password_plain)

    new_user = User(
        name=full_name,
        email=email_lc,
        phone=phone,
        nshe_id=nshe if role_lower == 'student' else None,
        employee_id=employee_id if role_lower == 'faculty' else None,
        role_id=role_obj.id,
        major_id=major.id if major else None,
        department_id=dept.id,
        password_hash=password_hash,
    )

    db.session.add(new_user)
    try:
        db.session.commit()
    except IntegrityError as ie:
        db.session.rollback()
        msg = str(ie.orig).lower()
        if 'email' in msg:
            flash('This email is already registered.', 'signup')
        elif 'nshe' in msg:
            flash('This NSHE ID is already registered.', 'signup')
        elif 'employee' in msg:
            flash('This Employee ID is already registered.', 'signup')
        else:
            flash('Could not create the account due to a database constraint.', 'signup')
        return render_signup_page(role_lower)

    login_user(new_user, remember=True)
    flash('Account created successfully!', 'auth')

    if role_lower == 'faculty':
        return redirect(url_for('faculty_ui.faculty_dashboard'))
    return redirect(url_for('student_ui.student_dashboard'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    session.pop('_flashes', None)

    if request.method == 'POST':
        email = _email_lower(request.form.get('email'))
        password = request.form.get('password') or ''
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password.', 'login')
            return render_template('login.html')

        login_user(user, remember=remember)
        flash('Login successful.', 'auth')

        role_name = (user.role.name if user.role else '').lower()
        if role_name == 'faculty':
            return redirect(url_for('faculty_ui.faculty_dashboard'))
        return redirect(url_for('student_ui.student_dashboard'))

    return render_template('login.html')

@auth.route('/logout', methods=['POST', 'GET'])
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out.', 'logout')
    return redirect(url_for('auth.login'))


# ==========================================================
# Password Reset (Forgot Password)
# ==========================================================
# Optional email sending: works if Flask-Mail is configured.
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

try:
    from flask_mail import Message
    from . import mail  # only if you initialized Mail() in __init__.py
    _MAIL_OK = True
except Exception:
    _MAIL_OK = False

def _serializer():
    # Uses your existing SECRET_KEY
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

def _make_token(email):
    return _serializer().dumps(email, salt='password-reset-salt')

def _read_token(token, max_age=3600):
    try:
        return _serializer().loads(token, salt='password-reset-salt', max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None

@auth.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = _email_lower(request.form.get('email'))
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("If that email exists, a reset option will appear.", "reset")
            return render_template("forgot_password.html", user=None)

        # Determine hint
        if user.role.name.lower() == "student":
            hint = f"Your default password was your NSHE ID"
        else:
            hint = f"Your default password was your Employee ID"

        return render_template("reset_password.html", user=user, hint=hint)

    return render_template("forgot_password.html")
    


@auth.route('/reset_password', methods=['POST'])
def reset_password():
    email = _email_lower(request.form.get('email'))
    current_password = request.form.get('current_password') or ""
    new_password = request.form.get('new_password') or ""
    confirm_password = request.form.get('confirm_password') or ""

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("Invalid request. User not found.", "reset")
        return redirect(url_for('auth.forgot_password'))

    # Verify current password
    if not check_password_hash(user.password_hash, current_password):
        flash("Current password is incorrect.", "reset")
        return render_template("reset_password.html", user=user)

    # Check new passwords match
    if new_password != confirm_password:
        flash("New passwords do not match.", "reset")
        return render_template("reset_password.html", user=user)

    # Optional: enforce strong password
    if len(new_password) < 8:
        flash("Password must be at least 8 characters.", "reset")
        return render_template("reset_password.html", user=user)

    # Save new password
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()

    flash("Password updated successfully. Please log in.", "reset")
    return redirect(url_for("auth.login"))
