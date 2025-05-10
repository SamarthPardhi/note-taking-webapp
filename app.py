from flask import Flask, request, jsonify, render_template
import os
import datetime
import markdown
import uuid
from pathlib import Path
import logging
import json # For potentially storing labels if not just relying on dirs

app = Flask(__name__)

DATA_DIR = Path("data")
# LABELS_FILE = DATA_DIR / "labels.json" # Option to store labels

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_current_labels():
    """Gets labels by scanning subdirectories in DATA_DIR."""
    if not DATA_DIR.exists():
        return []
    return sorted([d.name for d in DATA_DIR.iterdir() if d.is_dir()])

def ensure_data_dir_and_label(label_name):
    """Ensures DATA_DIR and a specific label directory exist."""
    DATA_DIR.mkdir(exist_ok=True)
    label_dir = DATA_DIR / label_name
    label_dir.mkdir(exist_ok=True)
    # Optionally update a labels.json file if you're managing labels explicitly
    # current_labels = get_current_labels()
    # if label_name not in current_labels:
        # Add to labels.json or other tracking mechanism

# Initial directory creation based on some default labels if needed,
# or just let them be created on demand.
# For this example, we'll rely on directories being created by save_note or a new /add_label route.
# def initialize_default_labels():
#     default_labels = ["idea", "paste", "joke"] # Initial set
#     for label in default_labels:
#         ensure_data_dir_and_label(label)

def save_note(content, label):
    ensure_data_dir_and_label(label) # Ensure label directory exists
    timestamp = datetime.datetime.now().isoformat()
    # Use a UUID for more robust unique filenames, especially if timestamps could collide
    unique_id = uuid.uuid4().hex
    filename = f"{timestamp.replace(':', '-').replace('.', '-')}-{unique_id[:8]}.md"
    filepath = DATA_DIR / label / filename
    
    title_content = content.split('\n', 1)[0] # First line as potential title
    title = title_content[:70] + '...' if len(title_content) > 70 else title_content

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"---\n")
        f.write(f"timestamp: {timestamp}\n")
        f.write(f"label: {label}\n")
        # More robust title extraction, e.g., from first H1 or first line
        f.write(f"title: {title}\n") 
        f.write(f"---\n\n")
        f.write(content)
    return timestamp, filename # Return filename for potential immediate use

def get_notes():
    notes = []
    current_labels = get_current_labels()
    for label in current_labels:
        label_dir = DATA_DIR / label
        # No need to check label_dir.exists() as get_current_labels already ensures these are dirs
        for filepath in label_dir.glob("*.md"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    full_content = f.read()
                    # Improved metadata parsing
                    if "---\n" not in full_content:
                        logger.warning(f"Metadata delimiter not found at start in {filepath}")
                        # Fallback: treat whole file as content, generate metadata
                        notes.append({
                            "timestamp": datetime.datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
                            "label": label,
                            "title": filepath.stem[:50], # Fallback title
                            "content": full_content,
                            "filename": filepath.name
                        })
                        continue

                    try:
                        metadata_section, body = full_content.split("---\n\n", 1)
                        metadata_content = metadata_section.replace("---", "").strip()
                    except ValueError: # If split fails due to missing second "---"
                        logger.warning(f"Metadata section not properly terminated in {filepath}")
                        # Fallback: take content after first "---" as body if possible
                        parts = full_content.split("---\n", 1)
                        if len(parts) > 1:
                            body = parts[1] # Everything after the first "---"
                            metadata_content = "" # No reliable metadata
                        else: # Unlikely, but if only "---" and nothing else
                            body = full_content
                            metadata_content = ""


                    metadata_dict = {}
                    if metadata_content:
                        for line in metadata_content.split("\n"):
                            if ": " not in line:
                                logger.warning(f"Skipping malformed metadata line in {filepath}: {line}")
                                continue
                            key, value = line.split(": ", 1)
                            metadata_dict[key.strip()] = value.strip()
                    
                    # Ensure essential fields, provide defaults if missing from parsed metadata
                    note_timestamp = metadata_dict.get("timestamp", datetime.datetime.fromtimestamp(filepath.stat().st_mtime).isoformat())
                    note_label = metadata_dict.get("label", label) # Fallback to directory label
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

def delete_note_file(label, filename): # Renamed to avoid conflict with flask route name
    filepath = DATA_DIR / label / filename
    if filepath.exists():
        try:
            filepath.unlink()
            logger.info(f"Deleted note: {filepath}")
            # If label directory becomes empty, optionally delete it
            if not any(filepath.parent.iterdir()):
                logger.info(f"Label directory {filepath.parent} is empty, removing.")
                filepath.parent.rmdir()
            return True
        except Exception as e:
            logger.error(f"Error deleting file {filepath}: {e}")
            return False
    return False


def update_note_content(label, filename, new_content): # Renamed
    filepath = DATA_DIR / label / filename
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                current_full_content = f.read()
            
            # Preserve existing metadata
            metadata_section = ""
            if current_full_content.startswith("---"):
                try:
                    metadata_section, _ = current_full_content.split("---\n\n", 1)
                    metadata_section += "---\n\n" # Add back the delimiter
                except ValueError: # If "---" is present but not the full block
                    metadata_section = f"---\ntimestamp: {datetime.datetime.now().isoformat()}\nlabel: {label}\ntitle: {new_content.splitlines()[0][:50]}\n---\n\n"
            else: # No metadata, create it
                 metadata_section = f"---\ntimestamp: {datetime.datetime.now().isoformat()}\nlabel: {label}\ntitle: {new_content.splitlines()[0][:50]}\n---\n\n"


            with open(filepath, "w", encoding="utf-8") as f:
                f.write(metadata_section)
                f.write(new_content)
            logger.info(f"Updated note: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error updating file {filepath}: {e}")
            return False
    return False

@app.route("/")
def index():
    ensure_data_dir_and_label("idea") # Ensure at least one default label/dir exists for startup
    current_labels = get_current_labels()
    return render_template("index.html", labels=current_labels)

@app.route("/add_label", methods=["POST"])
def add_label_route():
    data = request.json
    new_label = data.get("label_name", "").strip()
    if not new_label:
        return jsonify({"error": "Label name cannot be empty"}), 400
    if "/" in new_label or "\\" in new_label: # Basic validation
        return jsonify({"error": "Invalid characters in label name"}), 400
    
    current_labels = get_current_labels()
    if new_label in current_labels:
        return jsonify({"error": "Label already exists", "labels": current_labels}), 400 # Or success if already exists

    ensure_data_dir_and_label(new_label)
    logger.info(f"Added new label: {new_label}")
    return jsonify({"success": True, "message": f"Label '{new_label}' added.", "labels": get_current_labels()}), 201


@app.route("/save", methods=["POST"])
def save():
    data = request.json
    content = data.get("content")
    label = data.get("label")
    current_labels = get_current_labels() # Get current labels

    if not content or not label:
        return jsonify({"error": "Content and label are required"}), 400
    
    # If the label is new and not in current_labels, it will be created by save_note via ensure_data_dir_and_label
    # No explicit check against a fixed LABELS list here anymore.
    
    try:
        timestamp, filename = save_note(content, label)
        return jsonify({"timestamp": timestamp, "filename": filename, "label": label, "labels": get_current_labels()}), 201
    except Exception as e:
        logger.error(f"Error in /save route: {e}")
        return jsonify({"error": "Failed to save note"}), 500


@app.route("/notes", methods=["GET"])
def notes_route(): # Renamed to avoid conflict
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
            if lower_search in note['content'].lower() or \
               lower_search in note['title'].lower() or \
               (note.get('label') and lower_search in note['label'].lower())
        ]
        
    return jsonify(filtered_notes)

@app.route("/delete", methods=["POST"])
def delete():
    data = request.json
    label = data.get("label")
    filename = data.get("filename")
    # No check against fixed LABELS needed, just check if label and filename are provided
    if not label or not filename:
        return jsonify({"error": "Label and filename are required"}), 400
    if delete_note_file(label, filename):
        return jsonify({"success": True, "labels": get_current_labels()})
    else:
        return jsonify({"error": "Failed to delete note or note not found"}), 404


@app.route("/update", methods=["POST"])
def update():
    data = request.json
    label = data.get("label") # Original label
    filename = data.get("filename")
    content = data.get("content") # New content
    # new_label = data.get("new_label", label) # If allowing label change on update

    if not label or not filename or content is None: # Check content is not None
        return jsonify({"error": "Original label, filename, and content are required"}), 400

    # For simplicity, this example doesn't handle changing a note's label during an update,
    # which would involve moving the file. It only updates content within the same label/file.
    if update_note_content(label, filename, content):
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to update note or note not found"}), 404

if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True) # Ensure base data directory exists at start
    app.run(debug=True)