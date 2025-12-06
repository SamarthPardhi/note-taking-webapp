from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import datetime
from functools import wraps
import logging
import uuid 

# --- Configuration and Initialization ---
app = Flask(__name__)

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///zazu_notes.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_super_secret_dev_key_change_me')

db = SQLAlchemy(app)

# Configuration
DEVELOPMENT_TOKEN = "abraca"
ADMIN_EMAIL = "bravesamarth@gmail.com"
SUPPORT_EMAIL = "bravesamarth@gmail.com"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128)) 
    is_admin = db.Column(db.Boolean, default=False)
    notes = db.relationship('Note', backref='author', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.datetime.now)
    content = db.Column(db.Text, nullable=False)
    label = db.Column(db.String(50), default='idea')
    title = db.Column(db.String(100))

    def __repr__(self):
        return f'<Note {self.id}: {self.title}>'

# --- Utility Functions ---

def token_required(f):
    """Decorator to enforce the development token access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('token_authenticated'):
            return redirect(url_for('token_login_route'))
        
        # In this simple token mode, we assume a single user (ID 1) or Admin
        current_user_id = session.get('user_id', 1) 
        user = db.session.get(User, current_user_id)
        if not user:
            create_default_admin()
            user = db.session.get(User, 1)

        kwargs['current_user'] = user
        return f(*args, **kwargs)
    return decorated_function

def get_current_labels(user_id):
    labels = db.session.query(Note.label).filter_by(user_id=user_id).distinct().all()
    return sorted([label[0] for label in labels if label[0] and label[0].lower() != 'all'])

def create_default_admin():
    if not db.session.get(User, 1):
        admin = User(name="Admin User", email=ADMIN_EMAIL, is_admin=True)
        admin.set_password('admin_password_placeholder') 
        db.session.add(admin)
        db.session.commit()
        logger.info("Default admin user created.")

# --- Note Operations ---

def save_note(content, label, user_id):
    title = content.split('\n', 1)[0][:70] + '...' if len(content.split('\n', 1)[0]) > 70 else content.split('\n', 1)[0]
    new_note = Note(content=content, label=label, title=title, user_id=user_id)
    db.session.add(new_note)
    db.session.commit()
    return new_note.timestamp.isoformat(), new_note.id

def delete_note_by_id(note_id, user_id):
    note = db.session.get(Note, note_id)
    if note and note.user_id == user_id:
        db.session.delete(note)
        db.session.commit()
        return True
    return False

def update_note_content(note_id, new_content, new_label, user_id):
    note = db.session.get(Note, note_id)
    if note and note.user_id == user_id:
        note.content = new_content
        note.label = new_label
        note.title = new_content.split('\n', 1)[0][:70] + '...' if len(new_content.split('\n', 1)[0]) > 70 else new_content.split('\n', 1)[0]
        db.session.commit()
        return True
    return False

# --- Routes ---

@app.before_request
def setup_user_and_db():
    if not os.path.exists('zazu_notes.db'):
        with app.app_context():
            db.create_all()
            create_default_admin()

@app.route("/", methods=["GET", "POST"])
@app.route("/token_login", methods=["GET", "POST"])
def token_login_route():
    if session.get('token_authenticated'):
        return redirect(url_for('index'))
    
    if request.method == "POST":
        token = request.form.get("token")
        if token == DEVELOPMENT_TOKEN:
            session['token_authenticated'] = True
            session['user_id'] = 1 # Default to Admin ID 1
            return redirect(url_for('index'))
        else:
            flash("Invalid access token.", 'error')
            return redirect(url_for('token_login_route'))

    return render_template('token_login.html', support_email=SUPPORT_EMAIL)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        data = request.json
        name = data.get('name')
        email = data.get('email')
        
        if not name or not email:
            return jsonify({"error": "Name and email are required"}), 400
        
        if db.session.execute(db.select(User).filter_by(email=email)).scalar():
            return jsonify({"error": "User with this email already exists"}), 400
        
        new_user = User(name=name, email=email)
        new_user.set_password(str(uuid.uuid4())) # Dummy password
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return jsonify({"success": True, "message": f"Sign up successful. Please wait for the admin ({ADMIN_EMAIL}) to share your access token.", "admin_email": ADMIN_EMAIL}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": "Failed to save user data."}), 500
    return jsonify({"error": "Use POST to sign up."}), 405

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('token_login_route'))

@app.route("/notes_app")
@token_required
def index(current_user):
    current_labels = get_current_labels(current_user.id)
    return render_template("index.html", labels=current_labels, is_admin=current_user.is_admin, current_user=current_user)

@app.route("/admin")
@token_required
def admin_dashboard(current_user):
    if not current_user.is_admin:
        flash("Access Denied: You are not an admin.", 'error')
        return redirect(url_for('index'))
    users = db.session.execute(db.select(User)).scalars().all()
    return render_template("admin_dashboard.html", users=users, token=DEVELOPMENT_TOKEN)

# --- API Routes ---

@app.route("/add_label", methods=["POST"])
@token_required
def add_label_route(current_user):
    data = request.json
    new_label = data.get("label", "").strip().lower()
    if not new_label or not new_label.isalnum():
        return jsonify({"error": "Invalid label"}), 400
    return jsonify({"success": True, "labels": get_current_labels(current_user.id)}), 201

@app.route("/save", methods=["POST"])
@token_required
def save(current_user):
    data = request.json
    content = data.get("content")
    label = data.get("label")
    if not content or not label: return jsonify({"error": "Missing data"}), 400
    try:
        timestamp, note_id = save_note(content, label, current_user.id)
        return jsonify({"timestamp": timestamp, "id": note_id, "label": label, "labels": get_current_labels(current_user.id)}), 201
    except Exception as e:
        logger.error(f"Error saving note: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/notes", methods=["GET"])
@token_required
def notes_route(current_user):
    label_filter = request.args.get('label')
    search_term = request.args.get('search')
    query = db.select(Note).filter_by(user_id=current_user.id).order_by(Note.timestamp.desc())
    notes = db.session.execute(query).scalars()
    
    filtered_notes = []
    for note in notes:
        if label_filter and label_filter != 'all' and note.label != label_filter: continue
        if search_term:
            low_s = search_term.lower()
            if not (low_s in note.content.lower() or low_s in note.title.lower()): continue
        
        filtered_notes.append({
            "id": note.id,
            "timestamp": note.timestamp.isoformat(),
            "label": note.label,
            "title": note.title,
            "content": note.content,
            "filename": str(note.id)
        })
    return jsonify(filtered_notes)

@app.route("/delete", methods=["POST"])
@token_required
def delete(current_user):
    note_id = request.json.get("filename")
    if delete_note_by_id(int(note_id), current_user.id):
        return jsonify({"success": True, "labels": get_current_labels(current_user.id)})
    return jsonify({"error": "Failed"}), 404

@app.route("/update", methods=["POST"])
@token_required
def update(current_user):
    data = request.json
    note_id = int(data.get("filename"))
    if update_note_content(note_id, data.get("content"), data.get("label"), current_user.id):
        return jsonify({"success": True})
    return jsonify({"error": "Failed"}), 404

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_default_admin()
    app.run(debug=True)