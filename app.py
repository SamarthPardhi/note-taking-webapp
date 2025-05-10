from flask import Flask, request, jsonify, render_template
import os
import datetime
import uuid
from pathlib import Path
import logging

app = Flask(__name__)

DATA_DIR = Path("data")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_current_labels():
    if not DATA_DIR.exists():
        return []
    return sorted([d.name for d in DATA_DIR.iterdir() if d.is_dir()])

def ensure_data_dir_and_label(label_name):
    DATA_DIR.mkdir(exist_ok=True)
    label_dir = DATA_DIR / label_name
    label_dir.mkdir(exist_ok=True)

def save_note(content, label):
    ensure_data_dir_and_label(label)
    timestamp = datetime.datetime.now().isoformat()
    unique_id = uuid.uuid4().hex
    filename = f"{timestamp.replace(':', '-').replace('.', '-')}-{unique_id[:8]}.md"
    filepath = DATA_DIR / label / filename
    title = content.split('\n', 1)[0][:70] + '...' if len(content.split('\n', 1)[0]) > 70 else content.split('\n', 1)[0]
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"---\n")
        f.write(f"timestamp: {timestamp}\n")
        f.write(f"label: {label}\n")
        f.write(f"title: {title}\n")
        f.write(f"---\n\n")
        f.write(content)
    return timestamp, filename

def get_notes():
    notes = []
    current_labels = get_current_labels()
    for label in current_labels:
        label_dir = DATA_DIR / label
        for filepath in label_dir.glob("*.md"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    full_content = f.read()
                if "---\n" not in full_content:
                    notes.append({
                        "timestamp": datetime.datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
                        "label": label,
                        "title": filepath.stem[:50],
                        "content": full_content,
                        "filename": filepath.name
                    })
                    continue
                metadata_section, body = full_content.split("---\n\n", 1)
                metadata_content = metadata_section.replace("---", "").strip()
                metadata_dict = {}
                for line in metadata_content.split("\n"):
                    if ": " not in line:
                        continue
                    key, value = line.split(": ", 1)
                    metadata_dict[key.strip()] = value.strip()
                note_timestamp = metadata_dict.get("timestamp", datetime.datetime.fromtimestamp(filepath.stat().st_mtime).isoformat())
                note_label = metadata_dict.get("label", label)
                note_title = metadata_dict.get("title", body.split('\n',1)[0][:50] + "..." if body else filepath.stem[:50])
                notes.append({
                    "timestamp": note_timestamp,
                    "label": note_label,
                    "title": note_title,
                    "content": body.strip(),
                    "filename": filepath.name
                })
            except Exception as e:
                logger.error(f"Error processing {filepath}: {e}")
                continue
    return sorted(notes, key=lambda x: x["timestamp"], reverse=True)

def delete_note_file(label, filename):
    filepath = DATA_DIR / label / filename
    if filepath.exists():
        try:
            filepath.unlink()
            logger.info(f"Deleted note: {filepath}")
            if not any(filepath.parent.iterdir()):
                logger.info(f"Label directory {filepath.parent} is empty, removing.")
                filepath.parent.rmdir()
            return True
        except Exception as e:
            logger.error(f"Error deleting file {filepath}: {e}")
            return False
    return False

def update_note_content(original_label, filename, new_content, new_label):
    original_filepath = DATA_DIR / original_label / filename
    if not original_filepath.exists():
        return False
    if new_label != original_label:
        ensure_data_dir_and_label(new_label)
        new_filepath = DATA_DIR / new_label / filename
        try:
            original_filepath.rename(new_filepath)
            logger.info(f"Moved note from {original_filepath} to {new_filepath}")
        except Exception as e:
            logger.error(f"Error moving file: {e}")
            return False
    else:
        new_filepath = original_filepath
    try:
        with open(new_filepath, "r", encoding="utf-8") as f:
            current_full_content = f.read()
        if current_full_content.startswith("---"):
            metadata_section, _ = current_full_content.split("---\n\n", 1)
            metadata_lines = metadata_section.split("\n")
            updated_metadata = []
            for line in metadata_lines:
                if line.startswith("label:"):
                    updated_metadata.append(f"label: {new_label}")
                else:
                    updated_metadata.append(line)
            metadata_section = "\n".join(updated_metadata) + "\n---\n\n"
        else:
            metadata_section = f"---\ntimestamp: {datetime.datetime.now().isoformat()}\nlabel: {new_label}\ntitle: {new_content.splitlines()[0][:50]}\n---\n\n"
        with open(new_filepath, "w", encoding="utf-8") as f:
            f.write(metadata_section)
            f.write(new_content)
        logger.info(f"Updated note: {new_filepath}")
        return True
    except Exception as e:
        logger.error(f"Error updating file {new_filepath}: {e}")
        return False

@app.route("/")
def index():
    ensure_data_dir_and_label("idea")
    current_labels = get_current_labels()
    return render_template("index.html", labels=current_labels)

@app.route("/add_label", methods=["POST"])
def add_label_route():
    data = request.json
    new_label = data.get("label", "").strip().lower()
    if not new_label:
        return jsonify({"error": "Label name cannot be empty"}), 400
    if not new_label.isalnum():
        return jsonify({"error": "Label name must be alphanumeric"}), 400
    current_labels = get_current_labels()
    if new_label in current_labels:
        return jsonify({"error": "Label already exists"}), 400
    ensure_data_dir_and_label(new_label)
    logger.info(f"Added new label: {new_label}")
    return jsonify({"success": True, "message": f"Label '{new_label}' added.", "labels": get_current_labels()}), 201

@app.route("/save", methods=["POST"])
def save():
    data = request.json
    content = data.get("content")
    label = data.get("label")
    if not content or not label:
        return jsonify({"error": "Content and label are required"}), 400
    try:
        timestamp, filename = save_note(content, label)
        return jsonify({"timestamp": timestamp, "filename": filename, "label": label, "labels": get_current_labels()}), 201
    except Exception as e:
        logger.error(f"Error saving note: {e}")
        return jsonify({"error": f"Failed to save note: {str(e)}"}), 500

@app.route("/notes", methods=["GET"])
def notes_route():
    label_filter = request.args.get('label')
    search_term = request.args.get('search')
    all_notes = get_notes()
    filtered_notes = all_notes
    if label_filter and label_filter != 'all':
        filtered_notes = [note for note in filtered_notes if note['label'] == label_filter]
    if search_term:
        lower_search = search_term.lower()
        filtered_notes = [
            note for note in filtered_notes
            if lower_search in note['content'].lower() or
               lower_search in note['title'].lower() or
               (note.get('label') and lower_search in note['label'].lower())
        ]
    return jsonify(filtered_notes)

@app.route("/delete", methods=["POST"])
def delete():
    data = request.json
    label = data.get("label")
    filename = data.get("filename")
    if not label or not filename:
        return jsonify({"error": "Label and filename are required"}), 400
    if delete_note_file(label, filename):
        return jsonify({"success": True, "labels": get_current_labels()})
    else:
        return jsonify({"error": "Failed to delete note or note not found"}), 404

@app.route("/update", methods=["POST"])
def update():
    data = request.json
    original_label = data.get("original_label")
    filename = data.get("filename")
    content = data.get("content")
    new_label = data.get("label", original_label)
    if not original_label or not filename or content is None:
        return jsonify({"error": "Original label, filename, and content are required"}), 400
    if update_note_content(original_label, filename, content, new_label):
        return jsonify({"success": True, "new_label": new_label})
    else:
        return jsonify({"error": "Failed to update note or note not found"}), 404

if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    app.run(debug=True)