from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from app.models import db, User
from app import bcrypt, oauth

auth_bp = Blueprint('auth', __name__)


def _generate_unique_username(base_name):
    candidate = base_name.strip().replace(' ', '').lower() or 'googleuser'
    if not User.query.filter_by(username=candidate).first():
        return candidate

    suffix = 1
    while True:
        alt = f'{candidate}{suffix}'
        if not User.query.filter_by(username=alt).first():
            return alt
        suffix += 1


def _create_or_get_google_user(userinfo):
    email = (userinfo or {}).get('email')
    google_id = (userinfo or {}).get('sub') or (userinfo or {}).get('id')

    if not email or not google_id:
        return None

    user = User.query.filter_by(email=email).first()
    if user:
        if user.provider != 'google':
            user.provider = 'google'
            user.provider_id = google_id
        login_user(user)
        return user

    base_name = (userinfo or {}).get('given_name') or (userinfo or {}).get('name') or email.split('@')[0]
    username = _generate_unique_username(base_name)
    user = User(
        username=username,
        email=email,
        password_hash=bcrypt.generate_password_hash('google-oauth-user').decode('utf-8'),
        role='viewer',
        provider='google',
        provider_id=google_id,
    )
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return user

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash('You do not have permission to access that page.')
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password_hash and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('home'))
        flash('Invalid username or password.')
    return render_template('login.html')

@auth_bp.route('/google/login')
def login_google():
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@auth_bp.route('/google/callback')
def google_callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo') or oauth.google.userinfo()
    email = user_info['email']
    google_id = user_info['sub']

    user = User.query.filter_by(provider='google', provider_id=google_id).first()

    if not user:
        user = User.query.filter_by(email=email).first()
        if user:
            user.provider = 'google'
            user.provider_id = google_id
        else:
            username = email.split('@')[0]
            base_username = username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{counter}"
                counter += 1
            user = User(username=username, email=email, role='viewer',
                        provider='google', provider_id=google_id)
            db.session.add(user)

    db.session.commit()
    login_user(user)
    return redirect(url_for('home'))

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('That username is already taken.')
            return render_template('signup.html')
        hashed = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, password_hash=hashed, email=request.form.get('email'), role='viewer', provider='local')
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('home'))
    return render_template('signup.html')

@auth_bp.route('/signup/google')
def signup_google():
    if not hasattr(oauth, 'google'):
        flash('Google signup is not configured yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your environment.')
        return redirect(url_for('auth.signup'))
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))