import os
import sys

# Ensure root directory is on the python search path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app, init_db

# Initialize database/tables on cold start
init_db()

# Expose app for Vercel Serverless WSGI
handler = app
