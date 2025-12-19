from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import datetime
from functools import wraps
import logging
import uuid
import random
import string
import re

# --- Configuration and Initialization ---
app = Flask(__name__)

# Database Configuration
uri = os.getenv("DATABASE_URL", "sqlite:///project_alpha.db")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'project_alpha_secret_key')


db = SQLAlchemy(app)

# Configuration
ADMIN_EMAIL = "bravesamarth@gmail.com"
SUPPORT_EMAIL = "bravesamarth@gmail.com"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# --- Database Models ---

# Add 'theme' column to User model:
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    token = db.Column(db.String(6), unique=True, nullable=True)
    reference = db.Column(db.String(200), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    theme = db.Column(db.String(20), default='light')  # ADD THIS LINE
    notes = db.relationship('Note', backref='author', lazy='dynamic')
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Add new Feedback model:
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.now)

    def __repr__(self):
        return f'<Feedback {self.id}: {self.subject}>'


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

def generate_token(length=6):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login_route'))
        
        user_id = session.get('user_id')
        user = db.session.get(User, user_id)
        
        if not user:
            session.clear()
            return redirect(url_for('login_route'))

        kwargs['current_user'] = user
        return f(*args, **kwargs)
    return decorated_function

def get_current_labels(user_id):
    labels = db.session.query(Note.label).filter_by(user_id=user_id).distinct().all()
    # Sort labels alphabetically
    return sorted([label[0] for label in labels if label[0] and label[0].lower() != 'all'])

def create_default_admin():
    if not db.session.get(User, 1):
        admin_token = "ABRACA" 
        admin = User(
            name="Admin User", 
            email=ADMIN_EMAIL, 
            is_admin=True,
            token=admin_token,
            reference="Creator"
        )
        db.session.add(admin)
        db.session.commit()
        logger.info(f"Default admin user created. Token: {admin_token}")

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None




# --- Routes ---

@app.before_request
def setup_user_and_db():
    if not os.path.exists('project_alpha.db'):
        with app.app_context():
            db.create_all()
            create_default_admin()

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login_route():
    if session.get('authenticated'):
        return redirect(url_for('index'))
    
    if request.method == "POST":
        input_token = request.form.get("token", "").strip().upper()
        user = db.session.execute(db.select(User).filter_by(token=input_token)).scalar()
        
        if user:
            session['authenticated'] = True
            session['user_id'] = user.id
            return redirect(url_for('index'))
        else:
            flash("Invalid access token.", 'error')
            return redirect(url_for('login_route'))

    return render_template('token_login.html', support_email=SUPPORT_EMAIL)

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    reference = data.get('reference')
    
    if not name or not email:
        return jsonify({"error": "Name and email are required"}), 400

    if not is_valid_email(email):
        return jsonify({"error": "Invalid email address format"}), 400
    
    if db.session.execute(db.select(User).filter_by(email=email)).scalar():
        return jsonify({"error": "User with this email already exists"}), 400
    
    new_token = generate_token()
    while db.session.execute(db.select(User).filter_by(token=new_token)).scalar():
        new_token = generate_token()

    new_user = User(name=name, email=email, reference=reference, token=new_token)
    
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({
            "success": True, 
            "message": f"Request submitted. Admin will verify and send your token to {email}."
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to save request."}), 500

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login_route'))

# --- Main App ---

@app.route("/app")
@token_required
def index(current_user):
    current_labels = get_current_labels(current_user.id)
    return render_template(
        "index.html", 
        labels=current_labels, 
        is_admin=current_user.is_admin, 
        current_user=current_user,
        user_theme=current_user.theme  # ADD THIS LINE
    )

@app.route("/settings")
@token_required
def settings(current_user):
    return render_template("settings.html", current_user=current_user)

@app.route("/update_profile", methods=["POST"])
@token_required
def update_profile(current_user):
    data = request.json
    new_name = data.get("name")
    if not new_name:
        return jsonify({"error": "Name cannot be empty"}), 400
    try:
        current_user.name = new_name
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/delete_account", methods=["POST"])
@token_required
def delete_account(current_user):
    if current_user.is_admin and current_user.id == 1:
        return jsonify({"error": "Root admin cannot be deleted."}), 403
    try:
        db.session.query(Note).filter_by(user_id=current_user.id).delete()
        db.session.delete(current_user)
        db.session.commit()
        session.clear()
        return jsonify({"success": True, "redirect": url_for('login_route')})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/admin")
@token_required
def admin_dashboard(current_user):
    if not current_user.is_admin:
        flash("Access Denied.", 'error')
        return redirect(url_for('index'))
    
    users = db.session.execute(db.select(User)).scalars().all()
    feedback = db.session.execute(
        db.select(Feedback).order_by(Feedback.timestamp.desc())
    ).scalars().all()
    
    return render_template("admin_dashboard.html", users=users, feedback=feedback)


# --- Note API Routes ---

@app.route("/add_label", methods=["POST"])
@token_required
def add_label_route(current_user):
    data = request.json
    new_label = data.get("label", "").strip()
    if not new_label:
        return jsonify({"error": "Label cannot be empty"}), 400
    
    # Allow alphanumeric and spaces, hyphens
    if not re.match(r'^[a-zA-Z0-9\s\-]+$', new_label):
        return jsonify({"error": "Invalid characters. Only letters, numbers, spaces and hyphens allowed."}), 400
        
    return jsonify({"success": True, "labels": get_current_labels(current_user.id)}), 201

@app.route("/save", methods=["POST"])
@token_required
def save(current_user):
    data = request.json
    content = data.get("content")
    label = data.get("label")
    if not content or not label: return jsonify({"error": "Missing data"}), 400
    try:
        title = content.split('\n', 1)[0][:70] + '...' if len(content.split('\n', 1)[0]) > 70 else content.split('\n', 1)[0]
        new_note = Note(content=content, label=label, title=title, user_id=current_user.id)
        db.session.add(new_note)
        db.session.commit()
        return jsonify({"timestamp": new_note.timestamp.isoformat(), "id": new_note.id, "label": label, "labels": get_current_labels(current_user.id)}), 201
    except Exception as e:
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
        # Case insensitive filter comparison
        if label_filter and label_filter != 'all' and note.label.lower() != label_filter.lower(): continue
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
    note = db.session.get(Note, int(note_id))
    if note and note.user_id == current_user.id:
        db.session.delete(note)
        db.session.commit()
        return jsonify({"success": True, "labels": get_current_labels(current_user.id)})
    return jsonify({"error": "Failed"}), 404

@app.route("/update", methods=["POST"])
@token_required
def update(current_user):
    data = request.json
    note = db.session.get(Note, int(data.get("filename")))
    if note and note.user_id == current_user.id:
        note.content = data.get("content")
        note.label = data.get("label")
        note.title = note.content.split('\n', 1)[0][:70]
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"error": "Failed"}), 404


@app.route("/regenerate_token", methods=["POST"])
@token_required
def regenerate_token(current_user):
    """Regenerate user's access token"""
    try:
        # Generate new unique token
        new_token = generate_token()
        while db.session.execute(db.select(User).filter_by(token=new_token)).scalar():
            new_token = generate_token()
        
        # Update user's token
        current_user.token = new_token
        db.session.commit()
        
        return jsonify({
            "success": True,
            "token": new_token
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Token regeneration error: {e}")
        return jsonify({"error": "Failed to regenerate token"}), 500
    


# ==== NEW ROUTES ====

@app.route("/feedback")
@token_required
def feedback(current_user):
    return render_template("feedback.html", current_user=current_user)

@app.route("/submit_feedback", methods=["POST"])
@token_required
def submit_feedback(current_user):
    data = request.json
    feedback_type = data.get('type')
    subject = data.get('subject')
    message = data.get('message')
    
    if not all([feedback_type, subject, message]):
        return jsonify({"error": "All fields are required"}), 400
    
    try:
        new_feedback = Feedback(
            user_id=current_user.id,
            user_name=current_user.name,
            type=feedback_type,
            subject=subject,
            message=message
        )
        db.session.add(new_feedback)
        db.session.commit()
        return jsonify({"success": True}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Feedback submission error: {e}")
        return jsonify({"error": "Failed to submit feedback"}), 500


@app.route("/admin/update_token", methods=["POST"])
@token_required
def admin_update_token(current_user):
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({"error": "User ID required"}), 400
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    try:
        # Generate new unique token
        new_token = generate_token()
        while db.session.execute(db.select(User).filter_by(token=new_token)).scalar():
            new_token = generate_token()
        
        user.token = new_token
        db.session.commit()
        
        return jsonify({
            "success": True,
            "token": new_token
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Admin token update error: {e}")
        return jsonify({"error": "Failed to update token"}), 500

@app.route("/update_theme", methods=["POST"])
@token_required
def update_theme(current_user):
    data = request.json
    theme = data.get('theme')
    
    if theme not in ['light', 'dark', 'paper']:
        return jsonify({"error": "Invalid theme"}), 400
    
    try:
        current_user.theme = theme
        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Theme update error: {e}")
        return jsonify({"error": "Failed to update theme"}), 500



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_default_admin()
    app.run(host="0.0.0.0", port=8000, debug=True)