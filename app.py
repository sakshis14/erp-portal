import os
import sqlite3
import csv
import io
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, make_response, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta, date
import base64
import json
import uuid
import hashlib
import secrets
from PIL import Image
import pytz

app = Flask(__name__, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = 'static-key-for-development-12345-do-not-change-often' 
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=365)
app.config['REMEMBER_COOKIE_SECURE'] = False 
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_NAME'] = 'shramic_session'

UPLOAD_FOLDER = os.path.join('static', 'uploads')
PROFILE_PICS_FOLDER = os.path.join(UPLOAD_FOLDER, 'profiles')
TASK_FILES_FOLDER = os.path.join(UPLOAD_FOLDER, 'tasks')
SUBMISSION_FILES_FOLDER = os.path.join(UPLOAD_FOLDER, 'submissions')
DOCUMENT_FOLDER = os.path.join(UPLOAD_FOLDER, 'documents')
CERTIFICATE_FOLDER = os.path.join(UPLOAD_FOLDER, 'certificates')

for folder in [UPLOAD_FOLDER, PROFILE_PICS_FOLDER, TASK_FILES_FOLDER, 
               SUBMISSION_FILES_FOLDER, DOCUMENT_FOLDER, CERTIFICATE_FOLDER]:
    os.makedirs(folder, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROFILE_PICS_FOLDER'] = PROFILE_PICS_FOLDER
app.config['TASK_FILES_FOLDER'] = TASK_FILES_FOLDER
app.config['SUBMISSION_FILES_FOLDER'] = SUBMISSION_FILES_FOLDER
app.config['DOCUMENT_FOLDER'] = DOCUMENT_FOLDER
app.config['CERTIFICATE_FOLDER'] = CERTIFICATE_FOLDER

app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@shramic.com')

mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

login_manager.session_protection = 'basic' 

DATABASE = 'shramic_erp.db'

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(days=365)
    
    if current_user.is_authenticated:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            current_timestamp = format_datetime(get_current_datetime())
            cur.execute("UPDATE users SET updated_at = ? WHERE id = ?", 
                       (current_timestamp, current_user.id))
            conn.commit()
            conn.close()
        except:
            pass

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intern_id TEXT UNIQUE,
            usn TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            photo_url TEXT,
            status TEXT DEFAULT 'PENDING',
            is_admin BOOLEAN DEFAULT 0,
            department TEXT,
            join_date DATE,
            emergency_contact TEXT,
            address TEXT,
            last_login TIMESTAMP,
            login_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date DATE NOT NULL,
            check_in_time TIMESTAMP,
            check_out_time TIMESTAMP,
            work_hours REAL,
            location TEXT,
            ip_address TEXT,
            notes TEXT,
            status TEXT DEFAULT 'PRESENT',
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            file_url TEXT,
            assigned_to TEXT,
            assigned_by INTEGER,
            deadline DATE,
            priority TEXT DEFAULT 'MEDIUM',
            status TEXT DEFAULT 'ACTIVE',
            category TEXT,
            estimated_hours REAL,
            completion_percentage INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_by) REFERENCES users(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            content TEXT,
            file_url TEXT,
            file_type TEXT,
            file_size INTEGER,
            status TEXT DEFAULT 'PENDING',
            version INTEGER DEFAULT 1,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by INTEGER,
            feedback TEXT,
            grade TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (reviewed_by) REFERENCES users(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            recipient_id INTEGER,
            recipient_role TEXT,
            subject TEXT,
            content TEXT NOT NULL,
            is_broadcast BOOLEAN DEFAULT 0,
            is_read BOOLEAN DEFAULT 0,
            parent_message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (recipient_id) REFERENCES users(id),
            FOREIGN KEY (parent_message_id) REFERENCES messages(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_by INTEGER,
            priority TEXT DEFAULT 'NORMAL',
            category TEXT,
            target_roles TEXT,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            leave_type TEXT,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            total_days INTEGER,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            reviewed_by INTEGER,
            reviewed_at TIMESTAMP,
            admin_comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (reviewed_by) REFERENCES users(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            certificate_type TEXT NOT NULL,
            issue_date DATE DEFAULT CURRENT_DATE,
            certificate_number TEXT UNIQUE,
            file_url TEXT,
            verification_code TEXT UNIQUE,
            performance_grade TEXT,
            skills_acquired TEXT,
            projects_completed INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS document_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            document_type TEXT NOT NULL,
            document_name TEXT,
            file_url TEXT,
            status TEXT DEFAULT 'PENDING',
            verified_by INTEGER,
            verified_at TIMESTAMP,
            rejection_reason TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (verified_by) REFERENCES users(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS performance_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            reviewer_id INTEGER,
            review_period TEXT,
            technical_skills INTEGER,
            communication INTEGER,
            teamwork INTEGER,
            punctuality INTEGER,
            overall_rating REAL,
            strengths TEXT,
            improvements TEXT,
            comments TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (reviewer_id) REFERENCES users(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT,
            link TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            target_date DATE,
            status TEXT DEFAULT 'IN_PROGRESS',
            progress INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            skill_name TEXT NOT NULL,
            proficiency_level INTEGER,
            verified BOOLEAN DEFAULT 0,
            verified_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (verified_by) REFERENCES users(id)
        )
    ''')
    
    cur.execute("SELECT * FROM users WHERE email = ?", ('admin@shramic.com',))
    if not cur.fetchone():
        admin_password = generate_password_hash('admin123')
        current_date = format_datetime(get_current_date(), '%Y-%m-%d')
        cur.execute('''
            INSERT INTO users (intern_id, usn, full_name, phone, email, password_hash, 
                             role, status, is_admin, department, join_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('SHR-ADM-0000', 'ADMIN', 'System Admin', '0000000000', 
              'admin@shramic.com', admin_password, 'Admin', 'APPROVED', 1, 
              'Administration', current_date))
    
    conn.commit()
    conn.close()

TIMEZONE = pytz.timezone('Asia/Kolkata')

def get_current_datetime():
    return datetime.now(TIMEZONE)

def get_current_date():
    return get_current_datetime().date()

def format_datetime(dt, format_str='%Y-%m-%d %H:%M:%S'):
    if dt is None: return None
    if isinstance(dt, str): return dt
    return dt.strftime(format_str)

def log_activity(user_id, action, entity_type=None, entity_id=None, details=None):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO activity_logs (user_id, action, entity_type, entity_id, details, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, action, entity_type, entity_id, details, request.remote_addr))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Activity log error: {e}")

def create_notification(user_id, title, message, notification_type='info', link=None):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO notifications (user_id, title, message, type, link)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, title, message, notification_type, link))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Notification error: {e}")

def save_file(file_data, folder, prefix=''):
    if not file_data: return None
    try:
        if ',' in file_data:
            header, encoded = file_data.split(',', 1)
        else:
            encoded = file_data
        
        file_bytes = base64.b64decode(encoded)
        filename = f"{prefix}{uuid.uuid4().hex}.png"
        filepath = os.path.join(folder, filename)
        
        with open(filepath, 'wb') as f:
            f.write(file_bytes)
        
        return filename
    except Exception as e:
        print(f"File save error: {e}")
        return None

def calculate_work_hours(check_in, check_out):
    if not check_in or not check_out: return 0
    try:
        check_in_dt = datetime.strptime(check_in, '%Y-%m-%d %H:%M:%S')
        check_out_dt = datetime.strptime(check_out, '%Y-%m-%d %H:%M:%S')
        delta = check_out_dt - check_in_dt
        return round(delta.total_seconds() / 3600, 2)
    except:
        return 0

def generate_certificate_number():
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_part = secrets.token_hex(4).upper()
    return f"CERT-SHR-{timestamp}-{random_part}"

def generate_verification_code():
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:16].upper()

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.intern_id = user_data['intern_id']
        self.usn = user_data['usn']
        self.full_name = user_data['full_name']
        self.email = user_data['email']
        self.role = user_data['role']
        self.status = user_data['status']
        self.is_admin = bool(user_data['is_admin'])
        self.photo_url = user_data.get('photo_url')
        self.department = user_data.get('department')

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_data = cur.fetchone()
    conn.close()
    return User(dict(user_data)) if user_data else None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Access denied. Admin privileges required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def approved_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.status != 'APPROVED' and not current_user.is_admin:
            return render_template('auth/pending.html')
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = 0 AND status = 'APPROVED'")
    total_interns = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(DISTINCT department) as count FROM users WHERE is_admin = 0")
    total_depts = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM submissions")
    total_submissions = cur.fetchone()['count']
    
    attendance_rate = 0
    if total_interns > 0:
        cur.execute("SELECT COUNT(DISTINCT user_id) as count FROM attendance WHERE date = DATE('now', 'localtime')")
        present_today = cur.fetchone()['count']
        attendance_rate = int((present_today / total_interns) * 100)

    cur.execute("SELECT photo_url FROM users WHERE is_admin = 0 AND photo_url IS NOT NULL ORDER BY last_login DESC LIMIT 4")
    active_avatars = [row['photo_url'] for row in cur.fetchall()]
    
    cur.execute("""
        SELECT u.full_name, u.photo_url, t.title, s.status, s.submitted_at
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        JOIN tasks t ON s.task_id = t.id
        ORDER BY s.submitted_at DESC LIMIT 3
    """)
    recent_submissions = cur.fetchall()

    conn.close()

    return render_template('public/index.html',
                           total_interns=total_interns,
                           total_depts=total_depts,
                           attendance_rate=attendance_rate,
                           active_avatars=active_avatars,
                           recent_submissions=recent_submissions,
                           total_submissions=total_submissions)

@app.route('/about')
def about():
    return render_template('public/about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        try:
            if app.config['MAIL_USERNAME']:
                msg = Message('Contact Form Submission - Shramic ERP',
                            recipients=['admin@shramic.com'])
                current_time = format_datetime(get_current_datetime())
                msg.body = f"""
New contact form submission:

Name: {name}
Email: {email}
Message: {message}

Submitted at: {current_time}
"""
                mail.send(msg)
        except:
            pass
        
        flash('Thank you for contacting us! We will get back to you soon.', 'success')
        return redirect(url_for('contact'))
    
    return render_template('public/contact.html')


@app.route('/terms')
def terms():
    return render_template('public/terms.html')

@app.route('/privacy')
def privacy():
    return render_template('public/privacy.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            usn = request.form.get('usn').upper()
            full_name = request.form.get('full_name')
            phone = request.form.get('phone')
            email = request.form.get('email').lower()
            password = request.form.get('password')
            role = request.form.get('role')
            department = request.form.get('department')
            photo_data = request.form.get('photo_data')
            
            if not all([usn, full_name, phone, email, password, role]):
                flash('All fields are required.', 'error')
                return redirect(url_for('register'))
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("SELECT * FROM users WHERE usn = ? OR email = ?", (usn, email))
            if cur.fetchone():
                flash('USN or Email already registered.', 'error')
                conn.close()
                return redirect(url_for('register'))
            
            cur.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = 0")
            count = cur.fetchone()['count']
            intern_id = f"SHR-INT-{count + 1:04d}"
            
            photo_filename = None
            if photo_data:
                photo_filename = save_file(photo_data, PROFILE_PICS_FOLDER, f"{intern_id}_")
            
            password_hash = generate_password_hash(password)
            
            current_date = format_datetime(get_current_date(), '%Y-%m-%d')
            
            cur.execute('''
                INSERT INTO users (intern_id, usn, full_name, phone, email, password_hash, 
                                 role, photo_url, status, department, join_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (intern_id, usn, full_name, phone, email, password_hash, role, 
                  photo_filename, 'PENDING', department, current_date))
            
            conn.commit()
            conn.close()
            
            flash(f'Registration successful! Your Intern ID is {intern_id}. Awaiting admin approval.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'error')
            return redirect(url_for('register'))
    
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('intern_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email').lower()
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user_data = cur.fetchone()
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            current_timestamp = format_datetime(get_current_datetime())
            cur.execute('''
                UPDATE users 
                SET last_login = ?, login_count = login_count + 1 
                WHERE id = ?
            ''', (current_timestamp, user_data['id']))
            conn.commit()
            
            user = User(dict(user_data))
            login_user(user, remember=remember)
            
            # Log activity
            log_activity(user.id, 'USER_LOGIN')
            
            conn.close()
            
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            elif user.status == 'APPROVED':
                return redirect(url_for('intern_dashboard'))
            else:
                return render_template('auth/pending.html')
        else:
            conn.close()
            flash('Invalid email or password.', 'error')
    
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    log_activity(current_user.id, 'USER_LOGOUT')
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = 0")
    total_interns = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM users WHERE status = 'PENDING' AND is_admin = 0")
    pending_interns = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(DISTINCT user_id) as count FROM attendance WHERE date = DATE('now', 'localtime')")
    today_attendance = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM submissions WHERE status = 'PENDING'")
    pending_submissions = cur.fetchone()['count']

    cur.execute("SELECT COUNT(*) as count FROM users WHERE status = 'APPROVED' AND is_admin = 0")
    approved_count = cur.fetchone()['count']
    attendance_rate = int((today_attendance / approved_count) * 100) if approved_count > 0 else 0

    dates = []
    counts = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        cur.execute("SELECT COUNT(DISTINCT user_id) as count FROM attendance WHERE date = ?", (day,))
        cnt = cur.fetchone()['count']
        dates.append(datetime.strptime(day, '%Y-%m-%d').strftime('%b %d'))
        counts.append(cnt)
    
    chart_attendance = {'labels': dates, 'data': counts}

    cur.execute("""
        SELECT status, COUNT(*) as count FROM tasks 
        GROUP BY status
    """)
    task_rows = cur.fetchall()
    task_labels = [row['status'] for row in task_rows]
    task_data = [row['count'] for row in task_rows]
    chart_tasks = {'labels': task_labels, 'data': task_data}

    cur.execute("""
        SELECT u.id, u.full_name, u.intern_id, u.photo_url, a.check_in_time, a.location
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE a.date = DATE('now', 'localtime')
        ORDER BY a.check_in_time DESC LIMIT 6
    """)
    recent_attendance = cur.fetchall()

    cur.execute("""
        SELECT u.id, u.intern_id, u.full_name, u.photo_url, COUNT(s.id) as submissions
        FROM users u
        LEFT JOIN submissions s ON u.id = s.user_id AND s.status = 'APPROVED'
        WHERE u.is_admin = 0
        GROUP BY u.id
        ORDER BY submissions DESC
        LIMIT 5
    """)
    top_performers = cur.fetchall()

    conn.close()
    
    return render_template('admin/dashboard.html',
        total_interns=total_interns,
        pending_interns=pending_interns,
        today_attendance=today_attendance,
        attendance_rate=attendance_rate,
        pending_submissions=pending_submissions,
        recent_attendance=recent_attendance,
        top_performers=top_performers,
        chart_attendance=chart_attendance,
        chart_tasks=chart_tasks
    )
    
@app.route('/admin/interns')
@login_required
@admin_required
def admin_interns():
    conn = get_db_connection()
    cur = conn.cursor()
    
    role_filter = request.args.get('role', 'all')
    status_filter = request.args.get('status', 'all')
    department_filter = request.args.get('department', 'all')
    search = request.args.get('search', '')
    
    query = "SELECT * FROM users WHERE is_admin = 0"
    params = []
    
    if role_filter != 'all':
        query += " AND role = ?"
        params.append(role_filter)
    
    if status_filter != 'all':
        query += " AND status = ?"
        params.append(status_filter)
    
    if department_filter != 'all':
        query += " AND department = ?"
        params.append(department_filter)
    
    if search:
        query += " AND (full_name LIKE ? OR intern_id LIKE ? OR email LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    query += " ORDER BY created_at DESC"
    
    cur.execute(query, params)
    interns = cur.fetchall()
    
    # Get filter options
    cur.execute("SELECT DISTINCT role FROM users WHERE is_admin = 0")
    roles = [r['role'] for r in cur.fetchall()]
    
    cur.execute("SELECT DISTINCT department FROM users WHERE is_admin = 0 AND department IS NOT NULL")
    departments = [d['department'] for d in cur.fetchall()]
    
    conn.close()
    
    return render_template('admin/interns.html',
        interns=interns,
        roles=roles,
        departments=departments,
        current_role=role_filter,
        current_status=status_filter,
        current_department=department_filter,
        search=search
    )

@app.route('/admin/intern/<int:intern_id>')
@login_required
@admin_required
def admin_intern_detail(intern_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Basic Info
    cur.execute("SELECT * FROM users WHERE id = ?", (intern_id,))
    intern = cur.fetchone()
    
    if not intern:
        flash('Intern not found.', 'error')
        conn.close()
        return redirect(url_for('admin_dashboard'))
    
    cur.execute("""
        SELECT * FROM attendance 
        WHERE user_id = ? 
        ORDER BY date DESC 
        LIMIT 30
    """, (intern_id,))
    attendance_records = cur.fetchall()
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_days,
            SUM(work_hours) as total_hours,
            AVG(work_hours) as avg_hours
        FROM attendance
        WHERE user_id = ? AND check_in_time IS NOT NULL
    """, (intern_id,))
    attendance_stats = cur.fetchone()
    
    cur.execute("""
        SELECT s.*, t.title as task_title, t.priority 
        FROM submissions s
        LEFT JOIN tasks t ON s.task_id = t.id
        WHERE s.user_id = ?
        ORDER BY s.submitted_at DESC
    """, (intern_id,))
    submissions = cur.fetchall()
    
    cur.execute("""
        SELECT 'ATTENDANCE' as type, date as timestamp, 'Checked In' as details 
        FROM attendance WHERE user_id = ?
        UNION ALL
        SELECT 'SUBMISSION' as type, submitted_at as timestamp, 'Submitted Task' as details 
        FROM submissions WHERE user_id = ?
        ORDER BY timestamp DESC LIMIT 10
    """, (intern_id, intern_id))
    timeline = cur.fetchall()

    conn.close()
    
    return render_template('admin/intern_detail.html',
        intern=intern,
        attendance_records=attendance_records,
        stats=attendance_stats,
        submissions=submissions,
        timeline=timeline
    )
@app.route('/admin/approvals')
@login_required
@admin_required
def admin_approvals():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM users 
        WHERE status = 'PENDING' AND is_admin = 0 
        ORDER BY created_at DESC
    """)
    pending_interns = cur.fetchall()
    
    conn.close()
    return render_template('admin/approvals.html', pending_interns=pending_interns)

@app.route('/admin/approve/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_intern(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("UPDATE users SET status = 'APPROVED' WHERE id = ?", (user_id,))
    cur.execute("SELECT email, full_name, intern_id FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    
    conn.commit()
    
    create_notification(user_id, 'Account Approved! 🎉', 
                       'Your Shramic ERP account has been approved. You can now access all features.',
                       'success', url_for('intern_dashboard'))
    
    log_activity(current_user.id, 'APPROVE_INTERN', 'users', user_id, f"Approved {user['intern_id']}")
    
    conn.close()
    
    try:
        if app.config['MAIL_USERNAME']:
            msg = Message('Shramic ERP - Account Approved', recipients=[user['email']])
            msg.body = f"""Dear {user['full_name']},

Congratulations! Your Shramic ERP account has been approved.

Intern ID: {user['intern_id']}
Login: {url_for('login', _external=True)}

You can now access your dashboard and start your internship activities.

Best regards,
Shramic Team"""
            mail.send(msg)
    except Exception as e:
        print(f"Email error: {e}")
    
    flash(f'Intern approved successfully!', 'success')
    return redirect(url_for('admin_approvals'))

@app.route('/admin/reject/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def reject_intern(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT intern_id FROM users WHERE id = ?", (user_id,))
    intern = cur.fetchone()
    
    cur.execute("UPDATE users SET status = 'REJECTED' WHERE id = ?", (user_id,))
    conn.commit()
    
    log_activity(current_user.id, 'REJECT_INTERN', 'users', user_id, f"Rejected {intern['intern_id']}")
    
    conn.close()
    flash('Intern rejected.', 'info')
    return redirect(url_for('admin_approvals'))

@app.route('/admin/attendance')
@login_required
@admin_required
def admin_attendance():
    conn = get_db_connection()
    cur = conn.cursor()
    
    date_filter = request.args.get('date', format_datetime(get_current_date(), '%Y-%m-%d'))
    
    cur.execute("""
        SELECT u.id, u.intern_id, u.full_name, u.role, u.photo_url, u.department,
               a.check_in_time, a.check_out_time, a.work_hours, a.location
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE a.date = ?
        ORDER BY a.check_in_time DESC
    """, (date_filter,))
    today_attendance = cur.fetchall()
    
    cur.execute("""
        SELECT u.intern_id, u.full_name, u.role, u.department,
               COUNT(a.id) as days_present,
               SUM(a.work_hours) as total_hours,
               AVG(a.work_hours) as avg_hours
        FROM users u
        LEFT JOIN attendance a ON u.id = a.user_id 
            AND strftime('%Y-%m', a.date) = strftime('%Y-%m', 'now')
        WHERE u.is_admin = 0 AND u.status = 'APPROVED'
        GROUP BY u.id, u.intern_id, u.full_name, u.role, u.department
        ORDER BY days_present DESC
    """)
    monthly_summary = cur.fetchall()
    
    cur.execute("""
        SELECT u.id, u.intern_id, u.full_name, u.role, u.department, u.photo_url
        FROM users u
        WHERE u.is_admin = 0 AND u.status = 'APPROVED'
        AND u.id NOT IN (
            SELECT user_id FROM attendance WHERE date = ?
        )
    """, (date_filter,))
    absent_today = cur.fetchall()
    
    conn.close()
    
    return render_template('admin/attendance.html',
        today_attendance=today_attendance,
        monthly_summary=monthly_summary,
        absent_today=absent_today,
        date_filter=date_filter
    )

@app.route('/admin/attendance/export-csv')
@login_required
@admin_required
def export_attendance_csv():
    conn = get_db_connection()
    cur = conn.cursor()
    
    current_month = format_datetime(get_current_datetime(), '%Y-%m')
    month = request.args.get('month', current_month)
    
    cur.execute("""
        SELECT u.intern_id, u.full_name, u.role, u.department,
               a.date, a.check_in_time, a.check_out_time, a.work_hours, a.location
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        WHERE strftime('%Y-%m', a.date) = ?
        ORDER BY a.date DESC, u.intern_id
    """, (month,))
    
    records = cur.fetchall()
    conn.close()
    
    si = io.StringIO()
    writer = csv.writer(si)
    
    writer.writerow(['Intern ID', 'Full Name', 'Role', 'Department', 'Date', 
                    'Check In', 'Check Out', 'Work Hours', 'Location'])
    
    for record in records:
        writer.writerow([
            record['intern_id'],
            record['full_name'],
            record['role'],
            record['department'] or 'N/A',
            record['date'],
            record['check_in_time'],
            record['check_out_time'] or 'N/A',
            record['work_hours'] or 'N/A',
            record['location'] or 'N/A'
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=attendance_{month}.csv"
    output.headers["Content-type"] = "text/csv"
    
    log_activity(current_user.id, 'EXPORT_ATTENDANCE_CSV', details=f"Month: {month}")
    
    return output

@app.route('/admin/attendance/export-summary-csv')
@login_required
@admin_required
def export_attendance_summary_csv():
    conn = get_db_connection()
    cur = conn.cursor()
    
    current_month = format_datetime(get_current_datetime(), '%Y-%m')
    month = request.args.get('month', current_month)
    
    cur.execute("""
        SELECT u.intern_id, u.full_name, u.role, u.department,
               COUNT(a.id) as days_present,
               SUM(a.work_hours) as total_hours,
               AVG(a.work_hours) as avg_hours
        FROM users u
        LEFT JOIN attendance a ON u.id = a.user_id 
            AND strftime('%Y-%m', a.date) = ?
        WHERE u.is_admin = 0 AND u.status = 'APPROVED'
        GROUP BY u.id
        ORDER BY days_present DESC
    """, (month,))
    
    records = cur.fetchall()
    conn.close()
    
    si = io.StringIO()
    writer = csv.writer(si)
    
    writer.writerow(['Intern ID', 'Full Name', 'Role', 'Department', 
                    'Days Present', 'Total Hours', 'Average Hours'])
    
    for record in records:
        writer.writerow([
            record['intern_id'],
            record['full_name'],
            record['role'],
            record['department'] or 'N/A',
            record['days_present'] or 0,
            round(record['total_hours'] or 0, 2),
            round(record['avg_hours'] or 0, 2)
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=attendance_summary_{month}.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output

@app.route('/admin/tasks', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_tasks():
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        assigned_to = request.form.get('assigned_to')
        deadline = request.form.get('deadline')
        priority = request.form.get('priority', 'MEDIUM')
        category = request.form.get('category')
        estimated_hours = request.form.get('estimated_hours')
        file_data = request.form.get('file_data')
        
        file_filename = None
        if file_data:
            file_filename = save_file(file_data, TASK_FILES_FOLDER, 'task_')
        
        cur.execute("""
            INSERT INTO tasks (title, description, assigned_to, assigned_by, 
                             deadline, priority, category, estimated_hours, file_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, description, assigned_to, current_user.id, deadline, 
              priority, category, estimated_hours, file_filename))
        
        task_id = cur.lastrowid
        conn.commit()
        
        if assigned_to == 'ALL':
            cur.execute("SELECT id FROM users WHERE is_admin = 0 AND status = 'APPROVED'")
            for user in cur.fetchall():
                create_notification(user['id'], 'New Task Assigned', 
                                  f'Task: {title}', 'info', url_for('intern_tasks'))
        else:
            cur.execute("SELECT id FROM users WHERE intern_id = ? OR role = ?", 
                       (assigned_to, assigned_to))
            for user in cur.fetchall():
                create_notification(user['id'], 'New Task Assigned', 
                                  f'Task: {title}', 'info', url_for('intern_tasks'))
        
        log_activity(current_user.id, 'CREATE_TASK', 'tasks', task_id, f"Created: {title}")
        
        conn.close()
        flash('Task created successfully!', 'success')
        return redirect(url_for('admin_tasks'))
    
    cur.execute("""
        SELECT t.*, u.full_name as created_by_name,
               (SELECT COUNT(*) FROM submissions WHERE task_id = t.id) as submission_count
        FROM tasks t
        JOIN users u ON t.assigned_by = u.id
        ORDER BY t.created_at DESC
    """)
    tasks = cur.fetchall()
    
    cur.execute("SELECT intern_id, full_name FROM users WHERE is_admin = 0 AND status = 'APPROVED'")
    interns = cur.fetchall()
    
    cur.execute("SELECT DISTINCT role FROM users WHERE is_admin = 0")
    roles = [r['role'] for r in cur.fetchall()]
    
    conn.close()
    
    return render_template('admin/tasks.html', tasks=tasks, interns=interns, roles=roles)

@app.route('/admin/task/<int:task_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_task(task_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT title FROM tasks WHERE id = ?", (task_id,))
    task = cur.fetchone()
    
    cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    log_activity(current_user.id, 'DELETE_TASK', 'tasks', task_id, f"Deleted: {task['title']}")
    
    flash('Task deleted successfully!', 'success')
    return redirect(url_for('admin_tasks'))

@app.route('/admin/task/<int:task_id>/update', methods=['POST'])
@login_required
@admin_required
def update_task(task_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    status = request.form.get('status')
    completion_percentage = request.form.get('completion_percentage')
    
    cur.execute("""
        UPDATE tasks 
        SET status = ?, completion_percentage = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, completion_percentage, task_id))
    
    conn.commit()
    conn.close()
    
    log_activity(current_user.id, 'UPDATE_TASK', 'tasks', task_id)
    
    flash('Task updated successfully!', 'success')
    return redirect(url_for('admin_tasks'))

@app.route('/admin/submissions')
@login_required
@admin_required
def admin_submissions():
    conn = get_db_connection()
    cur = conn.cursor()
    
    status_filter = request.args.get('status', 'PENDING')
    
    cur.execute("""
        SELECT s.*, u.intern_id, u.full_name, u.photo_url, 
               t.title as task_title
        FROM submissions s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN tasks t ON s.task_id = t.id
        WHERE s.status = ?
        ORDER BY s.submitted_at DESC
    """, (status_filter,))
    submissions = cur.fetchall()
    
    conn.close()
    return render_template('admin/submissions.html', 
                         submissions=submissions, 
                         current_status=status_filter)

@app.route('/admin/submission/<int:submission_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_submission(submission_id):
    feedback = request.form.get('feedback', '')
    grade = request.form.get('grade', 'A')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT user_id FROM submissions WHERE id = ?", (submission_id,))
    submission = cur.fetchone()
    
    cur.execute("""
        UPDATE submissions 
        SET status = 'APPROVED', 
            reviewed_at = CURRENT_TIMESTAMP, 
            reviewed_by = ?, 
            feedback = ?,
            grade = ?
        WHERE id = ?
    """, (current_user.id, feedback, grade, submission_id))
    
    conn.commit()
    
    create_notification(submission['user_id'], 'Submission Approved! ✅', 
                       f'Your submission has been approved. Grade: {grade}',
                       'success', url_for('intern_submissions'))
    
    log_activity(current_user.id, 'APPROVE_SUBMISSION', 'submissions', submission_id)
    
    conn.close()
    flash('Submission approved!', 'success')
    return redirect(url_for('admin_submissions'))

@app.route('/admin/submission/<int:submission_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_submission(submission_id):
    feedback = request.form.get('feedback', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT user_id FROM submissions WHERE id = ?", (submission_id,))
    submission = cur.fetchone()
    
    cur.execute("""
        UPDATE submissions 
        SET status = 'REJECTED', 
            reviewed_at = CURRENT_TIMESTAMP, 
            reviewed_by = ?, 
            feedback = ?
        WHERE id = ?
    """, (current_user.id, feedback, submission_id))
    
    conn.commit()
    
    create_notification(submission['user_id'], 'Submission Needs Revision', 
                       'Your submission has been reviewed. Please check feedback.',
                       'warning', url_for('intern_submissions'))
    
    log_activity(current_user.id, 'REJECT_SUBMISSION', 'submissions', submission_id)
    
    conn.close()
    flash('Submission rejected.', 'info')
    return redirect(url_for('admin_submissions'))

@app.route('/admin/document-verification')
@login_required
@admin_required
def admin_document_verification():
    conn = get_db_connection()
    cur = conn.cursor()
    
    status_filter = request.args.get('status', 'PENDING')
    
    cur.execute("""
        SELECT dv.*, u.intern_id, u.full_name, u.photo_url
        FROM document_verifications dv
        JOIN users u ON dv.user_id = u.id
        WHERE dv.status = ?
        ORDER BY dv.uploaded_at DESC
    """, (status_filter,))
    documents = cur.fetchall()
    
    conn.close()
    return render_template('admin/document_verification.html',
                         documents=documents,
                         current_status=status_filter)

@app.route('/admin/document/<int:doc_id>/verify', methods=['POST'])
@login_required
@admin_required
def verify_document(doc_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT user_id FROM document_verifications WHERE id = ?", (doc_id,))
    doc = cur.fetchone()
    
    cur.execute("""
        UPDATE document_verifications 
        SET status = 'VERIFIED', verified_by = ?, verified_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (current_user.id, doc_id))
    
    conn.commit()
    
    create_notification(doc['user_id'], 'Document Verified ✅', 
                       'Your document has been verified successfully.',
                       'success')
    
    log_activity(current_user.id, 'VERIFY_DOCUMENT', 'document_verifications', doc_id)
    
    conn.close()
    flash('Document verified!', 'success')
    return redirect(url_for('admin_document_verification'))

@app.route('/admin/document/<int:doc_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_document(doc_id):
    reason = request.form.get('reason', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT user_id FROM document_verifications WHERE id = ?", (doc_id,))
    doc = cur.fetchone()
    
    cur.execute("""
        UPDATE document_verifications 
        SET status = 'REJECTED', 
            verified_by = ?, 
            verified_at = CURRENT_TIMESTAMP,
            rejection_reason = ?
        WHERE id = ?
    """, (current_user.id, reason, doc_id))
    
    conn.commit()
    
    create_notification(doc['user_id'], 'Document Rejected', 
                       f'Document rejected. Reason: {reason}',
                       'error')
    
    log_activity(current_user.id, 'REJECT_DOCUMENT', 'document_verifications', doc_id)
    
    conn.close()
    flash('Document rejected.', 'info')
    return redirect(url_for('admin_document_verification'))

@app.route('/admin/performance-reviews', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_performance_reviews():
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        review_period = request.form.get('review_period')
        technical_skills = request.form.get('technical_skills')
        communication = request.form.get('communication')
        teamwork = request.form.get('teamwork')
        punctuality = request.form.get('punctuality')
        strengths = request.form.get('strengths')
        improvements = request.form.get('improvements')
        comments = request.form.get('comments')
        
        overall_rating = (int(technical_skills) + int(communication) + 
                         int(teamwork) + int(punctuality)) / 4
        
        cur.execute("""
            INSERT INTO performance_reviews 
            (user_id, reviewer_id, review_period, technical_skills, communication, 
             teamwork, punctuality, overall_rating, strengths, improvements, comments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, current_user.id, review_period, technical_skills, communication,
              teamwork, punctuality, overall_rating, strengths, improvements, comments))
        
        conn.commit()
        
        create_notification(int(user_id), 'New Performance Review', 
                           f'Your {review_period} performance review is ready.',
                           'info', url_for('intern_profile'))
        
        log_activity(current_user.id, 'CREATE_PERFORMANCE_REVIEW', 'performance_reviews')
        
        conn.close()
        flash('Performance review submitted!', 'success')
        return redirect(url_for('admin_performance_reviews'))
    
    cur.execute("""
        SELECT pr.*, u.full_name, u.intern_id, u.photo_url
        FROM performance_reviews pr
        JOIN users u ON pr.user_id = u.id
        ORDER BY pr.created_at DESC
    """)
    reviews = cur.fetchall()
    
    cur.execute("""
        SELECT id, intern_id, full_name 
        FROM users 
        WHERE is_admin = 0 AND status = 'APPROVED'
    """)
    interns = cur.fetchall()
    
    conn.close()
    return render_template('admin/performance_reviews.html', 
                         reviews=reviews, 
                         interns=interns)

@app.route('/admin/announcements', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_announcements():
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        priority = request.form.get('priority', 'NORMAL')
        category = request.form.get('category')
        target_roles = request.form.get('target_roles', 'ALL')
        expires_at = request.form.get('expires_at')
        
        cur.execute("""
            INSERT INTO announcements 
            (title, content, created_by, priority, category, target_roles, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, content, current_user.id, priority, category, target_roles, expires_at))
        
        conn.commit()
        
        cur.execute("SELECT id FROM users WHERE is_admin = 0 AND status = 'APPROVED'")
        for user in cur.fetchall():
            create_notification(user['id'], f'📢 {title}', content, 'info', 
                              url_for('intern_announcements'))
        
        log_activity(current_user.id, 'CREATE_ANNOUNCEMENT', 'announcements')
        
        conn.close()
        flash('Announcement created successfully!', 'success')
        return redirect(url_for('admin_announcements'))
    
    cur.execute("""
        SELECT a.*, u.full_name as created_by_name
        FROM announcements a
        JOIN users u ON a.created_by = u.id
        ORDER BY a.created_at DESC
    """)
    announcements = cur.fetchall()
    
    conn.close()
    return render_template('admin/announcements.html', announcements=announcements)

@app.route('/admin/announcement/<int:announcement_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_announcement(announcement_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM announcements WHERE id = ?", (announcement_id,))
    conn.commit()
    conn.close()
    
    log_activity(current_user.id, 'DELETE_ANNOUNCEMENT', 'announcements', announcement_id)
    
    flash('Announcement deleted successfully!', 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/leaves')
@login_required
@admin_required
def admin_leaves():
    conn = get_db_connection()
    cur = conn.cursor()
    
    status_filter = request.args.get('status', 'PENDING')
    
    cur.execute("""
        SELECT l.*, u.intern_id, u.full_name, u.role, u.photo_url
        FROM leave_requests l
        JOIN users u ON l.user_id = u.id
        WHERE l.status = ?
        ORDER BY l.created_at DESC
    """, (status_filter,))
    leave_requests = cur.fetchall()
    
    conn.close()
    return render_template('admin/leaves.html', 
                         leave_requests=leave_requests, 
                         current_status=status_filter)

@app.route('/admin/leave/<int:leave_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_leave(leave_id):
    admin_comment = request.form.get('admin_comment', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT user_id FROM leave_requests WHERE id = ?", (leave_id,))
    leave = cur.fetchone()
    
    cur.execute("""
        UPDATE leave_requests 
        SET status = 'APPROVED', 
            reviewed_by = ?, 
            reviewed_at = CURRENT_TIMESTAMP,
            admin_comment = ?
        WHERE id = ?
    """, (current_user.id, admin_comment, leave_id))
    
    conn.commit()
    
    create_notification(leave['user_id'], 'Leave Approved ✅', 
                       'Your leave request has been approved.',
                       'success', url_for('intern_leave'))
    
    log_activity(current_user.id, 'APPROVE_LEAVE', 'leave_requests', leave_id)
    
    conn.close()
    flash('Leave request approved!', 'success')
    return redirect(url_for('admin_leaves'))

@app.route('/admin/leave/<int:leave_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_leave(leave_id):
    admin_comment = request.form.get('admin_comment', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT user_id FROM leave_requests WHERE id = ?", (leave_id,))
    leave = cur.fetchone()
    
    cur.execute("""
        UPDATE leave_requests 
        SET status = 'REJECTED', 
            reviewed_by = ?, 
            reviewed_at = CURRENT_TIMESTAMP,
            admin_comment = ?
        WHERE id = ?
    """, (current_user.id, admin_comment, leave_id))
    
    conn.commit()
    
    create_notification(leave['user_id'], 'Leave Request Update', 
                       f'Leave request rejected. {admin_comment}',
                       'warning', url_for('intern_leave'))
    
    log_activity(current_user.id, 'REJECT_LEAVE', 'leave_requests', leave_id)
    
    conn.close()
    flash('Leave request rejected.', 'info')
    return redirect(url_for('admin_leaves'))

@app.route('/admin/certificates')
@login_required
@admin_required
def admin_certificates():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT u.id, u.intern_id, u.full_name, u.role, u.department, u.usn,
               c.id as cert_id, c.certificate_number, c.issue_date
        FROM users u
        LEFT JOIN certificates c ON u.id = c.user_id
        WHERE u.is_admin = 0 AND u.status = 'APPROVED'
        ORDER BY u.full_name ASC
    """)
    interns = cur.fetchall()
    conn.close()
    return render_template('admin/certificates.html', interns=interns)

@app.route('/admin/generate-certificate/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def generate_certificate(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM certificates WHERE user_id = ?", (user_id,))
    if cur.fetchone():
        flash('Certificate already exists.', 'info')
        return redirect(url_for('admin_certificates'))

    cur.execute("SELECT COUNT(*) as count FROM submissions WHERE user_id = ? AND status = 'APPROVED'", (user_id,))
    projects = cur.fetchone()['count']
    
    cert_number = generate_certificate_number()
    verif_code = generate_verification_code()
    today = format_datetime(get_current_date(), '%Y-%m-%d')
    
    cur.execute("""
        INSERT INTO certificates 
        (user_id, certificate_type, certificate_number, verification_code,
         performance_grade, projects_completed, issue_date)
        VALUES (?, 'INTERNSHIP COMPLETION', ?, ?, 'A+', ?, ?)
    """, (user_id, cert_number, verif_code, projects, today))
    
    conn.commit()
    conn.close()
    flash('Certificate generated successfully!', 'success')
    return redirect(url_for('admin_certificates'))

@app.route('/admin/certificates/generate-all', methods=['POST'])
@login_required
@admin_required
def admin_generate_all_certificates():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM users WHERE is_admin = 0 AND status = 'APPROVED' AND id NOT IN (SELECT user_id FROM certificates)")
    interns = cur.fetchall()
    
    count = 0
    today = format_datetime(get_current_date(), '%Y-%m-%d')
    
    for intern in interns:
        u_id = intern['id']
        cur.execute("SELECT COUNT(*) as count FROM submissions WHERE user_id = ? AND status = 'APPROVED'", (u_id,))
        projects = cur.fetchone()['count']
        
        cur.execute("""
            INSERT INTO certificates 
            (user_id, certificate_type, certificate_number, verification_code, performance_grade, projects_completed, issue_date)
            VALUES (?, 'INTERNSHIP COMPLETION', ?, ?, 'A+', ?, ?)
        """, (u_id, generate_certificate_number(), generate_verification_code(), projects, today))
        count += 1
    
    conn.commit()
    conn.close()
    flash(f'Successfully generated {count} certificates.', 'success')
    return redirect(url_for('admin_certificates'))

@app.route('/admin/certificate/delete/<int:cert_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_certificate(cert_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT user_id FROM certificates WHERE id = ?", (cert_id,))
    cert_data = cur.fetchone()
    
    if cert_data:
        user_id = cert_data['user_id']
        cur.execute("DELETE FROM certificates WHERE id = ?", (cert_id,))
        conn.commit()
        
        create_notification(user_id, 'Certificate Retracted', 
                           'Your internship certificate has been retracted by the administrator. Please contact HR for details.', 
                           'warning')
        
    conn.close()
    flash('Certificate revoked successfully.', 'info')
    return redirect(url_for('admin_certificates'))

@app.route('/admin/certificate/view/<int:cert_id>')
@login_required
@admin_required
def admin_view_certificate(cert_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, u.full_name, u.usn, u.intern_id, u.role, u.department, u.join_date
        FROM certificates c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = ?
    """, (cert_id,))
    cert = cur.fetchone()
    conn.close()
    
    if not cert:
        flash('Certificate not found.', 'error')
        return redirect(url_for('admin_certificates'))
        
    return render_template('admin/view_certificate.html', cert=cert)

@app.route('/admin/messages', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_messages():
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == 'POST':
        recipient_id = request.form.get('recipient_id')
        subject = request.form.get('subject')
        content = request.form.get('content')
        is_broadcast = request.form.get('is_broadcast') == 'on'
        
        if is_broadcast:
            cur.execute("SELECT id FROM users WHERE is_admin = 0 AND status = 'APPROVED'")
            for user in cur.fetchall():
                cur.execute("""
                    INSERT INTO messages (sender_id, recipient_id, subject, content, is_broadcast)
                    VALUES (?, ?, ?, ?, 1)
                """, (current_user.id, user['id'], subject, content))
                
                create_notification(user['id'], f'New Message: {subject}', 
                                  content[:100], 'info', url_for('intern_messages'))
        else:
            cur.execute("""
                INSERT INTO messages (sender_id, recipient_id, subject, content)
                VALUES (?, ?, ?, ?)
            """, (current_user.id, recipient_id, subject, content))
            
            create_notification(int(recipient_id), f'New Message: {subject}', 
                              content[:100], 'info', url_for('intern_messages'))
        
        conn.commit()
        log_activity(current_user.id, 'SEND_MESSAGE', 'messages')
        
        conn.close()
        flash('Message sent successfully!', 'success')
        return redirect(url_for('admin_messages'))
    
    cur.execute("""
        SELECT m.*, u.full_name as recipient_name, u.intern_id
        FROM messages m
        LEFT JOIN users u ON m.recipient_id = u.id
        WHERE m.sender_id = ?
        ORDER BY m.created_at DESC
    """, (current_user.id,))
    sent_messages = cur.fetchall()
    
    cur.execute("""
        SELECT id, intern_id, full_name 
        FROM users 
        WHERE is_admin = 0 AND status = 'APPROVED'
    """)
    interns = cur.fetchall()
    
    conn.close()
    return render_template('admin/messages.html', 
                         sent_messages=sent_messages, 
                         interns=interns)

@app.route('/admin/analytics')
@login_required
@admin_required
def admin_analytics():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT date, COUNT(DISTINCT user_id) as count
        FROM attendance
        WHERE date >= DATE('now', '-30 days')
        GROUP BY date
        ORDER BY date
    """)
    attendance_trend = cur.fetchall()
    
    cur.execute("""
        SELECT role, COUNT(*) as count
        FROM users
        WHERE is_admin = 0
        GROUP BY role
    """)
    role_distribution = cur.fetchall()
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed
        FROM tasks
    """)
    task_stats = cur.fetchone()
    
    cur.execute("""
        SELECT u.intern_id, u.full_name, 
               COUNT(s.id) as submissions,
               AVG(CASE s.grade 
                   WHEN 'A+' THEN 4.0
                   WHEN 'A' THEN 3.7
                   WHEN 'B+' THEN 3.3
                   WHEN 'B' THEN 3.0
                   ELSE 2.5 
               END) as avg_grade
        FROM users u
        LEFT JOIN submissions s ON u.id = s.user_id AND s.status = 'APPROVED'
        WHERE u.is_admin = 0
        GROUP BY u.id
        ORDER BY submissions DESC, avg_grade DESC
        LIMIT 10
    """)
    top_performers = cur.fetchall()
    
    # Department-wise stats
    cur.execute("""
        SELECT department, COUNT(*) as count
        FROM users
        WHERE is_admin = 0 AND department IS NOT NULL
        GROUP BY department
    """)
    department_stats = cur.fetchall()
    
    conn.close()
    
    return render_template('admin/analytics.html',
        attendance_trend=attendance_trend,
        role_distribution=role_distribution,
        task_stats=task_stats,
        top_performers=top_performers,
        department_stats=department_stats
    )

@app.route('/intern/dashboard')
@login_required
@approved_required
def intern_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM tasks
        WHERE (assigned_to = ? OR assigned_to = ? OR assigned_to = 'ALL')
        AND status = 'ACTIVE'
        ORDER BY deadline ASC, created_at DESC
        LIMIT 10
    """, (current_user.intern_id, current_user.role))
    tasks = cur.fetchall()
    
    cur.execute("""
        SELECT s.*, t.title as task_title
        FROM submissions s
        LEFT JOIN tasks t ON s.task_id = t.id
        WHERE s.user_id = ?
        ORDER BY s.submitted_at DESC
        LIMIT 5
    """, (current_user.id,))
    submissions = cur.fetchall()
    
    cur.execute("""
        SELECT COUNT(*) as count
        FROM attendance
        WHERE user_id = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')
    """, (current_user.id,))
    attendance_count = cur.fetchone()['count']
    
    cur.execute("""
        SELECT * FROM attendance
        WHERE user_id = ? AND date = DATE('now')
    """, (current_user.id,))
    today_attendance = cur.fetchone()
    
    cur.execute("""
        SELECT * FROM announcements
        WHERE (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        AND (target_roles = 'ALL' OR target_roles LIKE ?)
        ORDER BY priority DESC, created_at DESC
        LIMIT 5
    """, (f'%{current_user.role}%',))
    announcements = cur.fetchall()
    
    cur.execute("""
        SELECT COUNT(*) as count
        FROM tasks
        WHERE (assigned_to = ? OR assigned_to = ? OR assigned_to = 'ALL')
        AND status = 'ACTIVE'
    """, (current_user.intern_id, current_user.role))
    pending_tasks = cur.fetchone()['count']
    
    cur.execute("""
        SELECT COUNT(*) as count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (current_user.id,))
    unread_notifications = cur.fetchone()['count']
    
    cur.execute("""
        SELECT * FROM goals
        WHERE user_id = ? AND status = 'IN_PROGRESS'
        ORDER BY target_date ASC
        LIMIT 5
    """, (current_user.id,))
    goals = cur.fetchall()
    
    conn.close()
    
    return render_template('intern/dashboard.html',
        tasks=tasks,
        submissions=submissions,
        attendance_count=attendance_count,
        marked_today=today_attendance is not None,
        announcements=announcements,
        pending_tasks=pending_tasks,
        unread_notifications=unread_notifications,
        goals=goals
    )

@app.route('/intern/profile', methods=['GET', 'POST'])
@login_required
@approved_required
def intern_profile():
    if request.method == 'POST':
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            if request.form.get('update_profile'):
                phone = request.form.get('phone', '').strip()
                address = request.form.get('address', '').strip()
                emergency_contact = request.form.get('emergency_contact', '').strip()
                
                if phone:
                    cur.execute("UPDATE users SET phone = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                               (phone, current_user.id))
                if address:
                    cur.execute("UPDATE users SET address = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                               (address, current_user.id))
                if emergency_contact:
                    cur.execute("UPDATE users SET emergency_contact = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                               (emergency_contact, current_user.id))
                
                if 'cropped_image' in request.files:
                    photo_file = request.files['cropped_image']
                    if photo_file and photo_file.filename != '':
                        timestamp = int(datetime.now().timestamp())
                        filename = secure_filename(f"{current_user.intern_id}_{timestamp}.jpg")
                        filepath = os.path.join(PROFILE_PICS_FOLDER, filename)
                        
                        image = Image.open(photo_file.stream)
                        image = image.convert('RGB')
                        
                        image.thumbnail((400, 400), Image.Resampling.LANCZOS)
                        
                        image.save(filepath, 'JPEG', quality=90, optimize=True)
                        
                        cur.execute("UPDATE users SET photo_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                                   (filename, current_user.id))
                        
                        log_activity(current_user.id, 'UPDATE_PROFILE_PHOTO', details=f"Uploaded: {filename}")
                
                conn.commit()
                flash('Profile updated successfully! ✅', 'success')
                return jsonify({'success': True}) if 'X-Requested-With' in request.headers else redirect(url_for('intern_profile'))
            
            elif request.form.get('change_password'):
                current_password = request.form.get('current_password')
                new_password = request.form.get('new_password')
                confirm_password = request.form.get('confirm_password')
                
                cur.execute("SELECT password_hash FROM users WHERE id = ?", (current_user.id,))
                user = cur.fetchone()
                
                if not user:
                    flash('User not found!', 'error')
                elif not check_password_hash(user['password_hash'], current_password):
                    flash('Current password is incorrect!', 'error')
                elif new_password != confirm_password:
                    flash('New passwords do not match!', 'error')
                elif len(new_password) < 6:
                    flash('Password must be at least 6 characters!', 'error')
                else:
                    # Update password
                    hashed_password = generate_password_hash(new_password)
                    cur.execute("UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                               (hashed_password, current_user.id))
                    conn.commit()
                    log_activity(current_user.id, 'CHANGE_PASSWORD')
                    flash('Password changed successfully! 🔐', 'success')
                
                return redirect(url_for('intern_profile'))
        
        except Exception as e:
            conn.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
            print(f"Profile update error: {e}")
            return jsonify({'success': False, 'message': str(e)}) if 'X-Requested-With' in request.headers else redirect(url_for('intern_profile'))
        
        finally:
            conn.close()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT id, intern_id, usn, full_name, phone, email, role, status, 
                   photo_url, department, join_date, address, emergency_contact,
                   created_at, updated_at
            FROM users WHERE id = ?
        """, (current_user.id,))
        user = cur.fetchone()
        
        if not user:
            flash('Profile not found!', 'error')
            return redirect(url_for('intern_dashboard'))
        
        cur.execute("""
            SELECT 
                COUNT(*) as attendance_count,
                COALESCE(SUM(work_hours), 0) as total_hours
            FROM attendance 
            WHERE user_id = ?
        """, (current_user.id,))
        attendance_stats = cur.fetchone()
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_submissions,
                COUNT(CASE WHEN status = 'APPROVED' THEN 1 END) as approved_submissions
            FROM submissions 
            WHERE user_id = ?
        """, (current_user.id,))
        submission_stats = cur.fetchone()
        
        cur.execute("""
            SELECT COUNT(*) as tasks_completed
            FROM tasks t
            JOIN submissions s ON t.id = s.task_id
            WHERE s.user_id = ? AND s.status = 'APPROVED'
        """, (current_user.id,))
        tasks_stats = cur.fetchone()
        
        cur.execute("""
            SELECT COUNT(*) as reviews_count
            FROM performance_reviews
            WHERE user_id = ?
        """, (current_user.id,))
        reviews_count = cur.fetchone()['reviews_count']
        
        stats = {
            'attendance_count': attendance_stats['attendance_count'],
            'total_hours': round(float(attendance_stats['total_hours']), 1),
            'total_submissions': submission_stats['total_submissions'],
            'approved_submissions': submission_stats['approved_submissions'],
            'tasks_completed': tasks_stats['tasks_completed'],
            'reviews_count': reviews_count
        }
        
    except Exception as e:
        print(f"Profile stats error: {e}")
        stats = {'attendance_count': 0, 'total_hours': 0, 'total_submissions': 0, 
                'approved_submissions': 0, 'tasks_completed': 0, 'reviews_count': 0}
    
    finally:
        conn.close()
    
    return render_template('intern/profile.html', user=dict(user), stats=stats)

@app.route('/intern/attendance', methods=['GET', 'POST'])
@login_required
@approved_required
def intern_attendance():
    conn = get_db_connection()
    cur = conn.cursor()
    
    today = format_datetime(get_current_date(), '%Y-%m-%d')
    
    cur.execute("""
        SELECT * FROM attendance
        WHERE user_id = ? AND date = ?
    """, (current_user.id, today))
    today_attendance = cur.fetchone()
    
    cur.execute("""
        SELECT COUNT(*) as count 
        FROM attendance 
        WHERE user_id = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', date('now'))
    """, (current_user.id,))
    attendance_this_month = cur.fetchone()['count']
    
    cur.execute("""
        SELECT 
            COALESCE(SUM(work_hours), 0) as total_hours,
            COALESCE(AVG(work_hours), 0) as average_hours,
            COUNT(*) as working_days
        FROM attendance 
        WHERE user_id = ? AND work_hours IS NOT NULL
    """, (current_user.id,))
    hours_stats = cur.fetchone()
    
    cur.execute("""
        SELECT * FROM attendance 
        WHERE user_id = ? 
        ORDER BY date DESC 
        LIMIT 30
    """, (current_user.id,))
    attendance_history = cur.fetchall()
    
    conn.close()
    
    return render_template('intern/attendance.html',
        today_attendance=today_attendance,
        today_date=today,
        attendance_this_month=attendance_this_month,
        total_hours=hours_stats['total_hours'],
        average_hours=hours_stats['average_hours'],
        working_days=hours_stats['working_days'],
        attendance_history=attendance_history
    )


@app.route('/intern/attendance/mark', methods=['POST'])
@login_required
@approved_required
def intern_mark_attendance():
    today = format_datetime(get_current_date(), '%Y-%m-%d')
    now_time = get_current_datetime()
    location = request.form.get('location', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM attendance
        WHERE user_id = ? AND date = ?
    """, (current_user.id, today))
    existing = cur.fetchone()
    
    if existing and existing['check_in_time']:
        conn.close()
        return jsonify({
            'success': False,
            'message': 'Attendance already marked today!'
        })
    
    now_timestamp = format_datetime(now_time)
    
    if not existing:
        cur.execute("""
            INSERT INTO attendance (user_id, date, check_in_time, location, ip_address)
            VALUES (?, ?, ?, ?, ?)
        """, (current_user.id, today, now_timestamp, location, request.remote_addr))
    else:
        cur.execute("""
            UPDATE attendance
            SET check_in_time = ?, location = ?, ip_address = ?
            WHERE user_id = ? AND date = ?
        """, (now_timestamp, location, request.remote_addr, current_user.id, today))
    
    conn.commit()
    log_activity(current_user.id, 'MARK_ATTENDANCE')
    
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Attendance marked successfully!',
        'time': now_time.strftime('%H:%M:%S')
    })

@app.route('/intern/attendance/checkout', methods=['POST'])
@login_required
@approved_required
def intern_checkout():
    today = format_datetime(get_current_date(), '%Y-%m-%d')
    now_time = get_current_datetime()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT check_in_time FROM attendance
        WHERE user_id = ? AND date = ?
    """, (current_user.id, today))
    record = cur.fetchone()
    
    if not record:
        conn.close()
        return jsonify({'success': False, 'message': 'Please check in first!'})
    
    now_timestamp = format_datetime(now_time)
    
    work_hours = calculate_work_hours(record['check_in_time'], now_timestamp)
    
    cur.execute("""
        UPDATE attendance
        SET check_out_time = ?, work_hours = ?
        WHERE user_id = ? AND date = ?
    """, (now_timestamp, work_hours, current_user.id, today))
    
    conn.commit()
    log_activity(current_user.id, 'CHECKOUT_ATTENDANCE')
    
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Check-out recorded!',
        'time': now_time.strftime('%H:%M:%S'),
        'work_hours': work_hours
    })

@app.route('/intern/tasks')
@login_required
@approved_required
def intern_tasks():
    conn = get_db_connection()
    cur = conn.cursor()
    
    status_filter = request.args.get('status', 'all')
    
    query = """
        SELECT t.*,
               (SELECT COUNT(*) FROM submissions WHERE task_id = t.id AND user_id = ?) as submitted
        FROM tasks t
        WHERE (t.assigned_to = ? OR t.assigned_to = ? OR t.assigned_to = 'ALL')
    """
    params = [current_user.id, current_user.intern_id, current_user.role]
    
    if status_filter != 'all':
        query += " AND t.status = ?"
        params.append(status_filter)
    
    query += " ORDER BY t.deadline ASC, t.created_at DESC"
    
    cur.execute(query, params)
    tasks = cur.fetchall()
    
    conn.close()
    return render_template('intern/tasks.html', tasks=tasks, current_status=status_filter)

@app.route('/intern/submit', methods=['GET', 'POST'])
@login_required
@approved_required
def intern_submit():
    if request.method == 'POST':
        task_id = request.form.get('task_id')
        content = request.form.get('content')
        file_data = request.form.get('file_data')
        file_type = request.form.get('file_type', 'other')
        
        # Save file
        file_filename = None
        file_size = 0
        if file_data:
            file_filename = save_file(file_data, SUBMISSION_FILES_FOLDER, 
                                     f"{current_user.intern_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_")
            # Estimate file size from base64
            file_size = len(file_data) * 3 // 4
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO submissions (user_id, task_id, content, file_url, file_type, file_size)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (current_user.id, task_id if task_id else None, content, 
              file_filename, file_type, file_size))
        
        conn.commit()
        log_activity(current_user.id, 'SUBMIT_WORK', 'submissions')
        
        conn.close()
        flash('Submission sent successfully! Awaiting admin review.', 'success')
        return redirect(url_for('intern_submissions'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT t.*,
               (SELECT COUNT(*) FROM submissions WHERE task_id = t.id AND user_id = ?) as submitted
        FROM tasks t
        WHERE (t.assigned_to = ? OR t.assigned_to = ? OR t.assigned_to = 'ALL')
        AND t.status = 'ACTIVE'
        ORDER BY t.deadline ASC, t.created_at DESC
    """, (current_user.id, current_user.intern_id, current_user.role))
    tasks = cur.fetchall()
    
    conn.close()
    return render_template('intern/submit_work.html', tasks=tasks)

@app.route('/intern/submissions')
@login_required
@approved_required
def intern_submissions():
    conn = get_db_connection()
    cur = conn.cursor()
    
    status_filter = request.args.get('status', 'all')
    
    query = """
        SELECT s.*, t.title as task_title, r.full_name as reviewer_name
        FROM submissions s
        LEFT JOIN tasks t ON s.task_id = t.id
        LEFT JOIN users r ON s.reviewed_by = r.id
        WHERE s.user_id = ?
    """
    params = [current_user.id]
    
    if status_filter != 'all':
        query += " AND s.status = ?"
        params.append(status_filter)
    
    query += " ORDER BY s.submitted_at DESC"
    
    cur.execute(query, params)
    submissions = cur.fetchall()
    
    conn.close()
    return render_template('intern/submissions.html', 
                         submissions=submissions, 
                         current_status=status_filter)

@app.route('/intern/leave', methods=['GET', 'POST'])
@login_required
@approved_required
def intern_leave():
    if request.method == 'POST':
        leave_type = request.form.get('leave_type')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        reason = request.form.get('reason')
        
        # Calculate total days
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        total_days = (end - start).days + 1
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO leave_requests (user_id, leave_type, start_date, end_date, total_days, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (current_user.id, leave_type, start_date, end_date, total_days, reason))
        
        conn.commit()
        log_activity(current_user.id, 'REQUEST_LEAVE', 'leave_requests')
        
        conn.close()
        flash('Leave request submitted successfully!', 'success')
        return redirect(url_for('intern_leave'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT l.*, r.full_name as reviewer_name
        FROM leave_requests l
        LEFT JOIN users r ON l.reviewed_by = r.id
        WHERE l.user_id = ?
        ORDER BY l.created_at DESC
    """, (current_user.id,))
    leave_requests = cur.fetchall()
    
    conn.close()
    return render_template('intern/leave.html', leave_requests=leave_requests)

@app.route('/intern/announcements')
@login_required
@approved_required
def intern_announcements():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT a.*, u.full_name as created_by_name
        FROM announcements a
        JOIN users u ON a.created_by = u.id
        WHERE (a.expires_at IS NULL OR a.expires_at > CURRENT_TIMESTAMP)
        AND (a.target_roles = 'ALL' OR a.target_roles LIKE ?)
        ORDER BY a.priority DESC, a.created_at DESC
    """, (f'%{current_user.role}%',))
    announcements = cur.fetchall()
    
    conn.close()
    return render_template('intern/announcements.html', announcements=announcements)

@app.route('/intern/messages')
@login_required
@approved_required
def intern_messages():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get received messages
    cur.execute("""
        SELECT m.*, u.full_name as sender_name
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.recipient_id = ?
        ORDER BY m.created_at DESC
    """, (current_user.id,))
    messages = cur.fetchall()
    
    conn.close()
    return render_template('intern/messages.html', messages=messages)

@app.route('/intern/message/<int:message_id>/read', methods=['POST'])
@login_required
@approved_required
def mark_message_read(message_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE messages
        SET is_read = 1
        WHERE id = ? AND recipient_id = ?
    """, (message_id, current_user.id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/intern/goals', methods=['GET', 'POST'])
@login_required
@approved_required
def intern_goals():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        target_date = request.form.get('target_date')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO goals (user_id, title, description, target_date)
            VALUES (?, ?, ?, ?)
        """, (current_user.id, title, description, target_date))
        conn.commit()
        log_activity(current_user.id, 'CREATE_GOAL', 'goals')
        
        conn.close()
        flash('Goal created successfully!', 'success')
        return redirect(url_for('intern_goals'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM goals
        WHERE user_id = ?
        ORDER BY 
            CASE status 
                WHEN 'IN_PROGRESS' THEN 1
                WHEN 'COMPLETED' THEN 2
                ELSE 3
            END,
            target_date ASC
    """, (current_user.id,))
    goals = cur.fetchall()
    
    conn.close()
    return render_template('intern/goals.html', goals=goals)

@app.route('/intern/goal/<int:goal_id>/update', methods=['POST'])
@login_required
@approved_required
def update_goal(goal_id):
    progress = request.form.get('progress')
    status = request.form.get('status')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    update_fields = []
    params = []
    
    if progress:
        update_fields.append('progress = ?')
        params.append(progress)
    
    if status:
        update_fields.append('status = ?')
        params.append(status)
        if status == 'COMPLETED':
            update_fields.append('completed_at = CURRENT_TIMESTAMP')
    
    if update_fields:
        params.extend([goal_id, current_user.id])
        cur.execute(f"""
            UPDATE goals
            SET {', '.join(update_fields)}
            WHERE id = ? AND user_id = ?
        """, params)
        
        conn.commit()
    
    conn.close()
    flash('Goal updated!', 'success')
    return redirect(url_for('intern_goals'))

@app.route('/intern/skills', methods=['GET', 'POST'])
@login_required
@approved_required
def intern_skills():
    if request.method == 'POST':
        skill_name = request.form.get('skill_name')
        proficiency_level = request.form.get('proficiency_level')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO skills (user_id, skill_name, proficiency_level)
            VALUES (?, ?, ?)
        """, (current_user.id, skill_name, proficiency_level))
        
        conn.commit()
        log_activity(current_user.id, 'ADD_SKILL', 'skills')
        
        conn.close()
        flash('Skill added successfully!', 'success')
        return redirect(url_for('intern_skills'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM skills
        WHERE user_id = ?
        ORDER BY proficiency_level DESC, skill_name ASC
    """, (current_user.id,))
    skills = cur.fetchall()
    
    conn.close()
    return render_template('intern/skills.html', skills=skills)

@app.route('/intern/documents', methods=['GET', 'POST'])
@login_required
@approved_required
def intern_documents():
    if request.method == 'POST':
        document_type = request.form.get('document_type')
        document_name = request.form.get('document_name')
        file_data = request.form.get('file_data')
        
        file_filename = None
        if file_data:
            file_filename = save_file(file_data, DOCUMENT_FOLDER, 
                                     f"{current_user.intern_id}_doc_")
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO document_verifications (user_id, document_type, document_name, file_url)
            VALUES (?, ?, ?, ?)
        """, (current_user.id, document_type, document_name, file_filename))
        
        conn.commit()
        log_activity(current_user.id, 'UPLOAD_DOCUMENT', 'document_verifications')
        
        conn.close()
        flash('Document uploaded successfully! Awaiting verification.', 'success')
        return redirect(url_for('intern_documents'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT dv.*, v.full_name as verifier_name
        FROM document_verifications dv
        LEFT JOIN users v ON dv.verified_by = v.id
        WHERE dv.user_id = ?
        ORDER BY dv.uploaded_at DESC
    """, (current_user.id,))
    documents = cur.fetchall()
    
    conn.close()
    return render_template('intern/documents.html', documents=documents)

@app.route('/intern/notifications')
@login_required
@approved_required
def intern_notifications():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 50
    """, (current_user.id,))
    notifications = cur.fetchall()
    
    cur.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE user_id = ?
    """, (current_user.id,))
    
    conn.commit()
    conn.close()
    
    return render_template('intern/notifications.html', notifications=notifications)

@app.route('/intern/certificates')
@login_required
@approved_required
def intern_certificates():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, u.full_name, u.usn, u.department, u.role
        FROM certificates c
        JOIN users u ON c.user_id = u.id
        WHERE c.user_id = ? 
        ORDER BY c.issue_date DESC
    """, (current_user.id,))
    certificates = cur.fetchall()
    conn.close()
    return render_template('intern/certificates.html', certificates=certificates)

@app.route('/intern/certificate/view/<int:cert_id>')
@login_required
@approved_required
def intern_view_certificate(cert_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, u.full_name, u.usn, u.intern_id, u.role, u.department, u.join_date
        FROM certificates c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = ? AND (c.user_id = ? OR ?)
    """, (cert_id, current_user.id, current_user.is_admin))
    cert = cur.fetchone()
    conn.close()
    
    if not cert:
        flash('Certificate not found.', 'error')
        return redirect(url_for('intern_certificates'))
    return render_template('intern/view_certificate.html', cert=cert)

@app.route('/certificate/<code>')
def view_certificate(code):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*, u.full_name, u.usn, u.intern_id, u.role, u.department, u.join_date
        FROM certificates c
        JOIN users u ON c.user_id = u.id
        WHERE c.verification_code = ?
    """, (code,))
    cert = cur.fetchone()
    conn.close()
    
    if not cert:
        return "Invalid Certificate Link", 404
    return render_template('intern/view_certificate.html', cert=cert)

@app.route('/verify/certificate/', defaults={'code': None})
@app.route('/verify/certificate/<code>')
def verify_certificate(code):
    if not code:
        return render_template('public/verify_certificate_scanner.html')

    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT c.*, u.full_name, u.intern_id, u.role, u.department, u.usn, u.join_date
        FROM certificates c
        JOIN users u ON c.user_id = u.id
        WHERE c.verification_code = ?
    """, (code,))
    
    cert = cur.fetchone()
    conn.close()
    
    if cert:
        return render_template('public/verify_certificate.html', 
                               cert=cert, 
                               verified=True)
    else:
        return render_template('public/verify_certificate.html', 
                               verified=False, 
                               error="Invalid or expired verification code.")
        
@app.route('/api/notifications/unread')
@login_required
def api_unread_notifications():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT COUNT(*) as count
        FROM notifications
        WHERE user_id = ? AND is_read = 0
    """, (current_user.id,))
    
    count = cur.fetchone()['count']
    conn.close()
    
    return jsonify({'count': count})

@app.route('/api/health')
def health():
    return jsonify({'status': 'healthy', 'database': 'sqlite'}), 200

@app.route('/api/stats')
@login_required
def api_stats():
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) as total FROM users WHERE is_admin = 0")
    total_interns = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as count FROM attendance WHERE date = DATE('now')")
    today_attendance = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM submissions WHERE status = 'PENDING'")
    pending_submissions = cur.fetchone()['count']
    
    conn.close()
    
    return jsonify({
        'total_interns': total_interns,
        'today_attendance': today_attendance,
        'pending_submissions': pending_submissions
    })

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('static/uploads', filename)

@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500

@app.errorhandler(413)
def request_entity_too_large(e):
    flash('File too large. Maximum size is 16MB.', 'error')
    return redirect(request.url)

@app.context_processor
def inject_globals():
    unread_count = 0
    if current_user.is_authenticated:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) as count
                FROM notifications
                WHERE user_id = ? AND is_read = 0
            """, (current_user.id,))
            unread_count = cur.fetchone()['count']
            conn.close()
        except:
            pass
    
    return {
        'now': get_current_datetime(),
        'app_name': 'Shramic ERP',
        'unread_notifications': unread_count
    }
    
@app.before_request
def before_request():
    if current_user.is_authenticated:
        conn = get_db_connection()
        cur = conn.cursor()
        current_timestamp = format_datetime(get_current_datetime())
        cur.execute("""
            UPDATE users 
            SET updated_at = ? 
            WHERE id = ?
        """, (current_timestamp, current_user.id))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    init_db()
    print("🚀 SHRAMIC ERP SYSTEM - STARTED")
    app.run(debug=True, host='0.0.0.0', port=5000)