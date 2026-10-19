import os
import sys

# Ensure root directory is on the python search path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app, init_db

# Initialize database/tables safely on cold start
try:
    init_db()
except Exception as e:
    print(f"[Vault Cold Start] DB init note: {e}")

# Expose app and handler for Vercel Serverless WSGI
handler = app

