"""Analysis-history persistence and password-protected deletion.

NOTE: saving is now triggered ONLY by an explicit user action in the UI
("Save Analysis to History"). This module itself is unchanged - the
automatic call that used to happen on every upload was removed from app.py.
"""

import os
import glob
from datetime import datetime

# Anchor the history directory to the project root (this file's parent's parent),
# so it works regardless of the process's current working directory.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(_BASE_DIR, 'results', 'analysis_history')

DELETE_PASSWORD = "private"


def ensure_history_dir():
    os.makedirs(HISTORY_DIR, exist_ok=True)


def save_to_history(excel_bytes: bytes, filename: str) -> str:
    """Saves a new, uniquely-named analysis result. Never overwrites previous files."""
    ensure_history_dir()
    path = os.path.join(HISTORY_DIR, filename)
    # Extra safety: if a file with this exact name already exists (same-second re-run),
    # append a numeric suffix instead of overwriting.
    if os.path.exists(path):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(path):
            path = os.path.join(HISTORY_DIR, f"{base}_{counter}{ext}")
            counter += 1
    with open(path, 'wb') as f:
        f.write(excel_bytes)
    return path


def list_history() -> list:
    ensure_history_dir()
    files = sorted(glob.glob(os.path.join(HISTORY_DIR, "CT_DRL_Results_*.xlsx")), reverse=True)
    entries = []
    for f in files:
        stat = os.stat(f)
        entries.append({
            'filename': os.path.basename(f),
            'path': f,
            'size_kb': round(stat.st_size / 1024, 1),
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        })
    return entries


def delete_history_file(filename: str, password: str):
    """Returns (success: bool, message: str). Deletion requires the correct password."""
    if password != DELETE_PASSWORD:
        return False, "Incorrect password. Deletion cancelled."
    path = os.path.join(HISTORY_DIR, filename)
    if not os.path.exists(path):
        return False, "File not found."
    os.remove(path)
    return True, f"'{filename}' deleted successfully."