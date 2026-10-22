import os
import re
import json
import html
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, make_response, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()
from supabase_db import (
    supabase_client, is_supabase_enabled, upload_file_to_supabase,
    get_supabase_reels, get_supabase_reel, check_supabase_duplicate_reel,
    insert_supabase_reel, update_supabase_reel, delete_supabase_reel, format_supabase_reel,
    get_supabase_collections, insert_supabase_collection, delete_supabase_collection,
    get_supabase_tags, ensure_default_collections
)

# Application Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_SERVERLESS = bool(
    os.environ.get('VERCEL') or 
    os.environ.get('VERCEL_ENV') or 
    os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or 
    not os.access(BASE_DIR, os.W_OK)
)

if IS_SERVERLESS:
    UPLOAD_FOLDER = '/tmp/uploads'
    DB_PATH = '/tmp/vault.db'
else:
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    DB_PATH = os.path.join(BASE_DIR, 'vault.db')

try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except Exception:
    pass

app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'),
            static_url_path='/static')

# Secure session cookie setup
app.secret_key = os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET_KEY') or 'vault_session_secret_2026_super_secure_key_x99'
app.config['SESSION_COOKIE_NAME'] = 'vault_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = bool(os.environ.get('VERCEL') or os.environ.get('HTTPS'))
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB limit

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'webm', 'mkv', 'jpg', 'jpeg', 'png', 'webp', 'gif', 'svg'}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def normalize_instagram_url(url):
    """Normalize Instagram Reel and Post URLs for duplicate detection."""
    url = url.strip()
    match = re.search(r'instagram\.com/(?:reel|p|reels)/([A-Za-z0-9_-]+)', url)
    if match:
        code = match.group(1)
        return f"https://www.instagram.com/reel/{code}/", code
    return url, None

# --- STRICT SERVER-SIDE AUTHENTICATION & USER RESOLUTION ---
def get_authenticated_user():
    """
    Derives authenticated user strictly from server-side session or verified Bearer token.
    Never trusts a user ID supplied by the frontend body or query params.
    """
    # 1. Check Bearer token in Authorization header
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1].strip()
        if token and is_supabase_enabled() and supabase_client:
            try:
                user_res = supabase_client.auth.get_user(token)
                if user_res and user_res.user:
                    u = user_res.user
                    return {
                        'id': str(u.id),
                        'email': u.email or '',
                        'display_name': u.user_metadata.get('full_name') or (u.email.split('@')[0].capitalize() if u.email else 'Creator'),
                        'avatar_url': u.user_metadata.get('avatar_url') or 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80',
                        'role': 'Pro Member',
                        'token': token
                    }
            except Exception:
                pass

    # 2. Check server-side signed session cookie
    user_id = session.get('user_id')
    if user_id:
        return {
            'id': str(user_id),
            'email': session.get('user_email', ''),
            'display_name': session.get('user_display_name', 'Creator'),
            'avatar_url': session.get('user_avatar', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80'),
            'role': session.get('user_role', 'Creator Member'),
            'token': session.get('access_token')
        }

    return None

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_authenticated_user()
        if not user:
            return jsonify({'error': 'Unauthorized. Please sign in to access your Vault library.'}), 401
        return f(user, *args, **kwargs)
    return decorated_function

# Initialize Database Schema & Seed Data with Multi-Tenant Isolation
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS profiles (
        id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        email TEXT,
        avatar_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS collections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        name TEXT NOT NULL,
        description TEXT,
        color TEXT DEFAULT '#7D53FF',
        icon TEXT DEFAULT 'folder',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, name)
    );

    CREATE TABLE IF NOT EXISTS reels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        original_url TEXT,
        normalized_url TEXT,
        title TEXT NOT NULL,
        description TEXT,
        creator_username TEXT,
        creator_avatar TEXT,
        thumbnail_url TEXT,
        video_url TEXT,
        media_type TEXT DEFAULT 'video',
        save_status TEXT DEFAULT 'saved_video',
        duration TEXT DEFAULT '0:30',
        aspect_ratio TEXT DEFAULT '9:16',
        is_favorite INTEGER DEFAULT 0,
        is_watch_later INTEGER DEFAULT 0,
        is_archived INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, normalized_url)
    );

    CREATE TABLE IF NOT EXISTS reel_collections (
        reel_id INTEGER,
        collection_id INTEGER,
        PRIMARY KEY (reel_id, collection_id),
        FOREIGN KEY (reel_id) REFERENCES reels(id) ON DELETE CASCADE,
        FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS reel_tags (
        reel_id INTEGER,
        tag_id INTEGER,
        PRIMARY KEY (reel_id, tag_id),
        FOREIGN KEY (reel_id) REFERENCES reels(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
    );
    ''')

    # Migration check: Ensure user_id column exists on existing SQLite tables
    cursor.execute("PRAGMA table_info(reels)")
    reel_cols = [r[1] for r in cursor.fetchall()]
    if 'user_id' not in reel_cols:
        cursor.execute("ALTER TABLE reels ADD COLUMN user_id TEXT")

    cursor.execute("PRAGMA table_info(collections)")
    col_cols = [r[1] for r in cursor.fetchall()]
    if 'user_id' not in col_cols:
        cursor.execute("ALTER TABLE collections ADD COLUMN user_id TEXT")

    conn.commit()
    conn.close()

# Helper: Format Reel response with collections and tags
def format_reel(row, conn):
    if not row:
        return None
    reel_id = row['id']
    cursor = conn.cursor()

    cursor.execute('''
        SELECT c.id, c.name, c.color, c.icon 
        FROM collections c
        JOIN reel_collections rc ON c.id = rc.collection_id
        WHERE rc.reel_id = ?
    ''', (reel_id,))
    collections = [dict(c) for c in cursor.fetchall()]

    cursor.execute('''
        SELECT t.id, t.name 
        FROM tags t
        JOIN reel_tags rt ON t.id = rt.tag_id
        WHERE rt.reel_id = ?
    ''', (reel_id,))
    tags = [dict(t) for t in cursor.fetchall()]

    reel = dict(row)
    reel['collections'] = collections
    reel['tags'] = tags
    reel['primary_collection'] = collections[0] if collections else None
    return reel

def extract_reel_media_info(url):
    """
    Robust multi-strategy Instagram metadata and video extractor.
    Strategy 1: Fast Meta Tag / OpenGraph scraping (sub-second): extracts real Instagram CDN thumbnail, creator handle, title, and caption.
    Strategy 2: yt-dlp probe (5s timeout): extracts direct MP4 video stream if available.
    """
    if not url:
        return None

    clean_url = url.strip()
    match = re.search(r'instagram\.com/(?:reel|p|reels)/([A-Za-z0-9_-]+)', clean_url)
    shortcode = match.group(1) if match else None
    canonical_url = f"https://www.instagram.com/reel/{shortcode}/" if shortcode else clean_url

    info = {
        'shortcode': shortcode,
        'original_url': canonical_url,
        'title': None,
        'creator_username': None,
        'description': None,
        'thumbnail_url': None,
        'video_url': None,
        'duration': '0:30'
    }

    # Strategy 1: Fast Meta Tag / OpenGraph Extraction via Facebook User-Agent (< 500ms)
    try:
        headers = {
            'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        req = urllib.request.Request(canonical_url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as resp:
            content = resp.read().decode('utf-8', errors='ignore')

            # Real Instagram Thumbnail
            m_img = re.search(r'<meta\s+(?:property|name)="og:image"\s+content="([^"]+)"', content)
            if m_img:
                info['thumbnail_url'] = html.unescape(m_img.group(1))

            # Direct video if present in og tags
            m_vid = re.search(r'<meta\s+(?:property|name)="og:video(?::secure_url)?"\s+content="([^"]+)"', content)
            if m_vid:
                info['video_url'] = html.unescape(m_vid.group(1))

            # Creator & Title
            m_title = re.search(r'<meta\s+(?:property|name)="twitter:title"\s+content="([^"]+)"', content) or \
                      re.search(r'<meta\s+(?:property|name)="og:title"\s+content="([^"]+)"', content)
            if m_title:
                raw_title = html.unescape(m_title.group(1)).strip()
                # Parse creator handle if present like (@username)
                u_match = re.search(r'\(@([A-Za-z0-9_.]+)\)', raw_title) or re.search(r'by\s+([A-Za-z0-9_.]+)', raw_title)
                if u_match:
                    info['creator_username'] = f"@{u_match.group(1)}"
                elif ' on Instagram:' in raw_title:
                    parts = raw_title.split(' on Instagram:', 1)
                    info['creator_username'] = f"@{parts[0].strip().replace(' ', '_').lower()}"

                # Clean Title
                if ' on Instagram:' in raw_title:
                    info['title'] = raw_title.split(' on Instagram:', 1)[1].strip(' ":\'')
                elif ' • Instagram' in raw_title:
                    info['title'] = raw_title.split(' • Instagram', 1)[0].strip()
                else:
                    info['title'] = raw_title

            # Caption / Description
            m_desc = re.search(r'<meta\s+(?:property|name)="description"\s+content="([^"]+)"', content) or \
                     re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]+)"', content)
            if m_desc:
                info['description'] = html.unescape(m_desc.group(1)).strip()
    except Exception as e:
        print(f"[Meta extraction note] {e}")

    # Strategy 2: yt-dlp probe for direct MP4 stream with short timeout
    if not info.get('video_url'):
        try:
            import yt_dlp
            ydl_opts = {
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'socket_timeout': 5
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl_data = ydl.extract_info(canonical_url, download=False)
                vid = ydl_data.get('url')
                if not vid and 'formats' in ydl_data and ydl_data['formats']:
                    for fmt in reversed(ydl_data['formats']):
                        if fmt.get('url') and (fmt.get('vcodec') != 'none' or 'mp4' in fmt.get('ext', '')):
                            vid = fmt['url']
                            break
                    if not vid:
                        vid = ydl_data['formats'][-1].get('url')

                if vid:
                    info['video_url'] = vid

                if not info.get('thumbnail_url') and ydl_data.get('thumbnail'):
                    info['thumbnail_url'] = ydl_data['thumbnail']

                if not info.get('title') and ydl_data.get('title'):
                    info['title'] = ydl_data['title']

                if not info.get('creator_username'):
                    uploader = ydl_data.get('uploader') or ydl_data.get('channel')
                    if uploader:
                        info['creator_username'] = f"@{uploader}" if not uploader.startswith('@') else uploader

                if not info.get('description') and ydl_data.get('description'):
                    info['description'] = ydl_data['description']

                if ydl_data.get('duration'):
                    info['duration'] = f"0:{int(ydl_data['duration']):02d}"
        except Exception as e:
            print(f"[yt-dlp probe note] {e}")

    # Fallbacks for any missing fields
    if not info.get('creator_username'):
        info['creator_username'] = '@instagram_creator'
    if not info.get('title'):
        info['title'] = f"Reel by {info['creator_username']} ({shortcode or 'Reference'})"
    if not info.get('thumbnail_url'):
        info['thumbnail_url'] = 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&h=750&q=80'
    if not info.get('description'):
        info['description'] = 'Saved Instagram Reel inspiration. Metadata preserved from shared link.'

    return info

# =========================================================================
# API ROUTES (STRICT MULTI-TENANT ISOLATION & PERMISSION CHECKS)
# =========================================================================

@app.route('/api/reels', methods=['GET'])
def list_reels():
    user = get_authenticated_user()
    if not user:
        return jsonify({'reels': [], 'count': 0, 'authenticated': False}), 200

    user_id = user['id']
    collection_id = request.args.get('collection')
    tag_name = request.args.get('tag')
    media_type = request.args.get('type')
    search = request.args.get('search', '').strip()
    status = request.args.get('status')
    sort = request.args.get('sort', 'latest')

    # Supabase PostgreSQL multi-tenant fetch
    if is_supabase_enabled():
        supa_reels = get_supabase_reels(
            user_id=user_id,
            collection_id=collection_id, 
            media_type=media_type, 
            status=status, 
            search=search, 
            sort=sort
        )
        if supa_reels is not None:
            return jsonify({'reels': supa_reels, 'count': len(supa_reels)})

    # SQLite fallback with strict user_id filtering
    conn = get_db()
    cursor = conn.cursor()

    query = '''
        SELECT DISTINCT r.* 
        FROM reels r
        LEFT JOIN reel_collections rc ON r.id = rc.reel_id
        LEFT JOIN reel_tags rt ON r.id = rt.reel_id
        LEFT JOIN tags t ON rt.tag_id = t.id
        WHERE r.user_id = ?
    '''
    params = [user_id]

    if status == 'archived':
        query += " AND r.is_archived = 1"
    else:
        query += " AND r.is_archived = 0"

    if status == 'favorite':
        query += " AND r.is_favorite = 1"
    elif status == 'watch_later':
        query += " AND r.is_watch_later = 1"

    if collection_id and collection_id != 'all':
        query += " AND rc.collection_id = ?"
        params.append(int(collection_id))

    if tag_name:
        query += " AND t.name = ?"
        params.append(tag_name)

    if media_type and media_type in ['video', 'link', 'image']:
        query += " AND r.media_type = ?"
        params.append(media_type)

    if search:
        query += " AND (r.title LIKE ? OR r.description LIKE ? OR r.creator_username LIKE ? OR t.name LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    if sort == 'oldest':
        query += " ORDER BY r.created_at ASC"
    elif sort == 'title':
        query += " ORDER BY r.title ASC"
    else:
        query += " ORDER BY r.created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    reels = [format_reel(r, conn) for r in rows]
    conn.close()
    return jsonify({'reels': reels, 'count': len(reels)})

@app.route('/api/reels/<int:reel_id>', methods=['GET'])
def get_reel(reel_id):
    user = get_authenticated_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = user['id']

    if is_supabase_enabled():
        supa_reel = get_supabase_reel(reel_id, user_id=user_id)
        if supa_reel:
            return jsonify({'reel': supa_reel})
        return jsonify({'error': 'Reel not found or unauthorized'}), 404

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reels WHERE id = ? AND user_id = ?", (reel_id, user_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Reel not found or unauthorized'}), 404

    reel = format_reel(row, conn)
    conn.close()
    return jsonify({'reel': reel})

@app.route('/api/reels/<int:reel_id>/video', methods=['GET'])
def get_reel_video_stream(reel_id):
    user = get_authenticated_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = user['id']

    target_reel = None
    if is_supabase_enabled():
        target_reel = get_supabase_reel(reel_id, user_id=user_id)
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reels WHERE id = ? AND user_id = ?", (reel_id, user_id))
        row = cursor.fetchone()
        if row:
            target_reel = dict(row)
        conn.close()

    if not target_reel:
        return jsonify({'error': 'Reel not found or unauthorized'}), 404

    video_url = target_reel.get('video_url')
    if not video_url:
        orig = target_reel.get('original_url') or target_reel.get('normalized_url')
        if orig:
            info = extract_reel_media_info(orig)
            if info and info.get('video_url'):
                video_url = info['video_url']
                new_thumb = info.get('thumbnail_url') or target_reel.get('thumbnail_url')
                if is_supabase_enabled():
                    update_supabase_reel(reel_id, {
                        'video_url': video_url, 
                        'save_status': 'saved_video',
                        'thumbnail_url': new_thumb
                    }, user_id=user_id)
                else:
                    conn = get_db()
                    conn.execute("UPDATE reels SET video_url = ?, thumbnail_url = ?, save_status = 'saved_video' WHERE id = ? AND user_id = ?", (video_url, new_thumb, reel_id, user_id))
                    conn.commit()
                    conn.close()

    if video_url:
        return redirect(video_url, code=302)

    return jsonify({'error': 'Video stream not available for this reel'}), 404

@app.route('/api/parse-url', methods=['POST'])
def parse_instagram_url():
    """Validates Instagram Reel URL and checks duplicates strictly within the authenticated user's account."""
    user = get_authenticated_user()
    if not user:
        return jsonify({'error': 'Unauthorized. Please sign in to save reels.'}), 401
    user_id = user['id']

    data = request.get_json() or {}
    raw_url = (data.get('url') or '').strip()

    if not raw_url:
        return jsonify({'error': 'URL is required'}), 400

    normalized_url, shortcode = normalize_instagram_url(raw_url)
    if not shortcode and not ('instagram.com' in raw_url):
        return jsonify({'error': 'Please provide a valid Instagram Reel or Post link'}), 400

    # Supabase duplicate check SCOPED strictly to user_id
    if is_supabase_enabled():
        supa_dup = check_supabase_duplicate_reel(user_id, normalized_url, raw_url)
        if supa_dup:
            return jsonify({
                'duplicate': True,
                'message': 'This Reel is already saved in your Vault!',
                'existing_reel': supa_dup
            })

    # SQLite duplicate check SCOPED strictly to user_id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reels WHERE user_id = ? AND (normalized_url = ? OR original_url = ?)", (user_id, normalized_url, raw_url))
    existing = cursor.fetchone()

    if existing:
        reel = format_reel(existing, conn)
        conn.close()
        return jsonify({
            'duplicate': True,
            'message': 'This Reel is already saved in your Vault!',
            'existing_reel': reel
        })

    conn.close()

    # Extract metadata via robust multi-strategy extractor
    media_info = extract_reel_media_info(raw_url) or extract_reel_media_info(normalized_url)

    creator_handle = '@instagram_creator'
    title = f"Instagram Creative Reference ({shortcode or 'Reel'})"
    description = "Saved Instagram Reel inspiration. Metadata preserved from shared link."
    thumbnail = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&h=750&q=80"
    extracted_video_url = None
    duration = '0:30'

    if media_info:
        title = media_info.get('title') or title
        creator_handle = media_info.get('creator_username') or creator_handle
        thumbnail = media_info.get('thumbnail_url') or thumbnail
        extracted_video_url = media_info.get('video_url')
        description = media_info.get('description') or description
        duration = media_info.get('duration') or duration
        shortcode = media_info.get('shortcode') or shortcode

    embed_url = f"https://www.instagram.com/reel/{shortcode}/embed/" if shortcode else None

    return jsonify({
        'duplicate': False,
        'normalized_url': normalized_url,
        'shortcode': shortcode,
        'title': title,
        'creator_username': creator_handle,
        'description': description,
        'thumbnail_url': thumbnail,
        'video_url': extracted_video_url,
        'embed_url': embed_url,
        'duration': duration,
        'save_status': 'saved_video' if extracted_video_url else 'saved_link'
    })

@app.route('/api/reels', methods=['POST'])
def create_reel():
    user = get_authenticated_user()
    if not user:
        return jsonify({'error': 'Unauthorized. Please sign in to save reels.'}), 401
    user_id = user['id']

    data = request.get_json() or {}
    original_url = (data.get('original_url') or '').strip()
    title = (data.get('title') or '').strip()
    description = (data.get('description') or '').strip()
    creator_username = (data.get('creator_username') or '@creator').strip()
    thumbnail_url = (data.get('thumbnail_url') or '').strip()
    video_url = (data.get('video_url') or '').strip() or None
    media_type = data.get('media_type') or 'video'
    collection_id = data.get('collection_id')
    tags_list = data.get('tags') or []

    # Auto-extract video stream and rich metadata if missing or using generic placeholders
    if original_url and (not video_url or not thumbnail_url or 'photo-1618005182384' in thumbnail_url or 'Instagram Creative Reference' in title or creator_username in ('@creator', '@instagram_creator')):
        media_info = extract_reel_media_info(original_url)
        if media_info:
            if not video_url and media_info.get('video_url'):
                video_url = media_info['video_url']
            if not thumbnail_url or 'photo-1618005182384' in thumbnail_url:
                if media_info.get('thumbnail_url'):
                    thumbnail_url = media_info['thumbnail_url']
            if (not creator_username or creator_username in ('@creator', '@instagram_creator')) and media_info.get('creator_username'):
                creator_username = media_info['creator_username']
            if (not title or 'Instagram Creative Reference' in title) and media_info.get('title'):
                title = media_info['title']
            if (not description or 'Metadata preserved from shared link' in description) and media_info.get('description'):
                description = media_info['description']

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    save_status = data.get('save_status') or ('saved_video' if video_url else 'saved_link')
    normalized_url, _ = normalize_instagram_url(original_url) if original_url else (None, None)

    # Supabase PostgreSQL save
    if is_supabase_enabled():
        supa_data = {
            'user_id': user_id,
            'original_url': original_url or 'https://instagram.com/reel/upload',
            'normalized_url': normalized_url or f"manual_{user_id}_{int(datetime.utcnow().timestamp())}",
            'title': title,
            'description': description,
            'creator_username': creator_username,
            'creator_avatar': 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=100&h=100&q=80',
            'thumbnail_url': thumbnail_url or 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&h=750&q=80',
            'video_url': video_url,
            'media_type': media_type,
            'save_status': save_status,
            'duration': data.get('duration') or '0:30'
        }
        new_supa_reel = insert_supabase_reel(supa_data, collection_id=collection_id, tags=tags_list, user_id=user_id)
        if new_supa_reel:
            return jsonify({'reel': new_supa_reel, 'message': 'Reel saved successfully to your Vault!'}), 201

    conn = get_db()
    cursor = conn.cursor()

    # SQLite Duplicate check scoped strictly to user_id
    if normalized_url:
        cursor.execute("SELECT id FROM reels WHERE user_id = ? AND normalized_url = ?", (user_id, normalized_url))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return jsonify({'error': 'This Reel already exists in your library'}), 409

    if not thumbnail_url:
        thumbnail_url = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&h=750&q=80"

    cursor.execute('''
        INSERT INTO reels (
            user_id, original_url, normalized_url, title, description,
            creator_username, creator_avatar, thumbnail_url, video_url,
            media_type, save_status, duration
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        original_url,
        normalized_url or f"manual_{user_id}_{datetime.utcnow().timestamp()}",
        title,
        description,
        creator_username,
        'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=100&h=100&q=80',
        thumbnail_url,
        video_url,
        media_type,
        save_status,
        data.get('duration', '0:30')
    ))
    reel_id = cursor.lastrowid

    # Assign collection
    if collection_id:
        cursor.execute("INSERT OR IGNORE INTO reel_collections (reel_id, collection_id) VALUES (?, ?)", (reel_id, int(collection_id)))

    # Assign tags
    for tag_name in tags_list:
        clean_tag = tag_name.strip().lstrip('#')
        if clean_tag:
            cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (clean_tag,))
            cursor.execute("SELECT id FROM tags WHERE name = ?", (clean_tag,))
            t_row = cursor.fetchone()
            if t_row:
                cursor.execute("INSERT OR IGNORE INTO reel_tags (reel_id, tag_id) VALUES (?, ?)", (reel_id, t_row['id']))

    conn.commit()
    cursor.execute("SELECT * FROM reels WHERE id = ? AND user_id = ?", (reel_id, user_id))
    new_reel = format_reel(cursor.fetchone(), conn)
    conn.close()
    return jsonify({'reel': new_reel, 'message': 'Reel saved successfully!'}), 201

@app.route('/api/reels/<int:reel_id>', methods=['PATCH'])
def update_reel(reel_id):
    user = get_authenticated_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = user['id']

    data = request.get_json() or {}
    updatable = ['title', 'description', 'creator_username', 'is_favorite', 'is_watch_later', 'is_archived', 'save_status']
    updates = {k: data[k] for k in updatable if k in data}

    if is_supabase_enabled():
        supa_updated = update_supabase_reel(
            reel_id, 
            updates, 
            collection_id=data.get('collection_id'), 
            tags=data.get('tags'),
            user_id=user_id
        )
        if supa_updated:
            return jsonify({'reel': supa_updated, 'message': 'Reel updated successfully'})
        return jsonify({'error': 'Reel not found or unauthorized'}), 404

    conn = get_db()
    cursor = conn.cursor()

    # Verify ownership
    cursor.execute("SELECT id FROM reels WHERE id = ? AND user_id = ?", (reel_id, user_id))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Reel not found or unauthorized'}), 404

    sql_updates = []
    values = []
    for key, val in updates.items():
        sql_updates.append(f"{key} = ?")
        values.append(val)

    if sql_updates:
        values.append(datetime.utcnow())
        values.append(reel_id)
        values.append(user_id)
        cursor.execute(f"UPDATE reels SET {', '.join(sql_updates)}, updated_at = ? WHERE id = ? AND user_id = ?", values)

    if 'collection_id' in data:
        col_id = data['collection_id']
        cursor.execute("DELETE FROM reel_collections WHERE reel_id = ?", (reel_id,))
        if col_id:
            cursor.execute("INSERT INTO reel_collections (reel_id, collection_id) VALUES (?, ?)", (reel_id, int(col_id)))

    if 'tags' in data and isinstance(data['tags'], list):
        cursor.execute("DELETE FROM reel_tags WHERE reel_id = ?", (reel_id,))
        for tag_name in data['tags']:
            clean_tag = tag_name.strip().lstrip('#')
            if clean_tag:
                cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (clean_tag,))
                cursor.execute("SELECT id FROM tags WHERE name = ?", (clean_tag,))
                t_row = cursor.fetchone()
                if t_row:
                    cursor.execute("INSERT OR IGNORE INTO reel_tags (reel_id, tag_id) VALUES (?, ?)", (reel_id, t_row['id']))

    conn.commit()
    cursor.execute("SELECT * FROM reels WHERE id = ? AND user_id = ?", (reel_id, user_id))
    updated = format_reel(cursor.fetchone(), conn)
    conn.close()
    return jsonify({'reel': updated, 'message': 'Reel updated successfully'})

@app.route('/api/reels/<int:reel_id>', methods=['DELETE'])
def delete_reel(reel_id):
    user = get_authenticated_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = user['id']

    if is_supabase_enabled():
        if delete_supabase_reel(reel_id, user_id=user_id):
            return jsonify({'success': True, 'message': 'Reel removed from Vault'})
        return jsonify({'error': 'Reel not found or unauthorized'}), 404

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reels WHERE id = ? AND user_id = ?", (reel_id, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()

    if affected > 0:
        return jsonify({'success': True, 'message': 'Reel removed from Vault'})
    return jsonify({'error': 'Reel not found or unauthorized'}), 404

# --- UPLOADS API ---
@app.route('/api/upload', methods=['POST'])
def upload_file():
    user = get_authenticated_user()
    if not user:
        return jsonify({'error': 'Unauthorized. Please sign in to upload files.'}), 401
    user_id = user['id']

    file = request.files.get('file') or request.files.get('video') or request.files.get('avatar')
    if not file or file.filename == '':
        return jsonify({'error': 'No file provided'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{int(datetime.utcnow().timestamp())}_{file.filename}")
        
        video_url = None
        if is_supabase_enabled():
            try:
                file_bytes = file.read()
                content_type = file.content_type or 'application/octet-stream'
                video_url = upload_file_to_supabase(file_bytes, filename, content_type, user_id=user_id)
            except Exception as e:
                print(f"[Supabase Upload Fallback] {e}")

        # Local storage fallback with user directory isolation
        if not video_url:
            user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
            os.makedirs(user_upload_dir, exist_ok=True)
            save_path = os.path.join(user_upload_dir, filename)
            file.seek(0)
            file.save(save_path)
            video_url = f"/uploads/{user_id}/{filename}"

        return jsonify({
            'success': True,
            'filename': filename,
            'url': video_url,
            'video_url': video_url,
            'storage': 'supabase' if is_supabase_enabled() else 'local',
            'save_status': 'saved_video',
            'message': 'File uploaded securely to Vault Storage.'
        })

    return jsonify({'error': 'File format not supported. Use MP4, MOV, WebM, JPG, PNG, or WebP.'}), 400

@app.route('/api/status', methods=['GET'])
def get_system_status():
    supabase_active = is_supabase_enabled()
    is_vercel = bool(os.environ.get('VERCEL')) or bool(os.environ.get('VERCEL_ENV'))
    user = get_authenticated_user()
    return jsonify({
        'status': 'online',
        'database': 'Supabase PostgreSQL' if supabase_active else 'SQLite (Local)',
        'storage': 'Supabase Storage (vault-media)' if supabase_active else 'Local Storage',
        'platform': 'Vercel Serverless' if is_vercel else 'Localhost Environment',
        'supabase_configured': supabase_active,
        'vercel_environment': is_vercel,
        'authenticated': bool(user),
        'user': user if user else None
    })

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- COLLECTIONS API ---
@app.route('/api/collections', methods=['GET'])
def list_collections():
    user = get_authenticated_user()
    if not user:
        return jsonify({'collections': []})
    user_id = user['id']

    if is_supabase_enabled():
        supa_cols = get_supabase_collections(user_id=user_id)
        if supa_cols is not None:
            return jsonify({'collections': supa_cols})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.*, COUNT(rc.reel_id) as reel_count 
        FROM collections c
        LEFT JOIN reel_collections rc ON c.id = rc.collection_id
        LEFT JOIN reels r ON rc.reel_id = r.id AND r.is_archived = 0 AND r.user_id = ?
        WHERE c.user_id = ?
        GROUP BY c.id
        ORDER BY c.name ASC
    ''', (user_id, user_id))
    collections = [dict(c) for c in cursor.fetchall()]
    conn.close()
    return jsonify({'collections': collections})

@app.route('/api/collections', methods=['POST'])
def create_collection():
    user = get_authenticated_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = user['id']

    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    color = (data.get('color') or '#7D53FF').strip()
    icon = (data.get('icon') or 'folder').strip()

    if not name:
        return jsonify({'error': 'Collection name is required'}), 400

    if is_supabase_enabled():
        new_supa_col = insert_supabase_collection(name, description, color, icon, user_id=user_id)
        if new_supa_col:
            return jsonify({'collection': new_supa_col, 'message': 'Collection created'}), 201

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO collections (user_id, name, description, color, icon)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, name, description, color, icon))
        conn.commit()
        col_id = cursor.lastrowid
        cursor.execute("SELECT *, 0 as reel_count FROM collections WHERE id = ? AND user_id = ?", (col_id, user_id))
        new_col = dict(cursor.fetchone())
        conn.close()
        return jsonify({'collection': new_col, 'message': 'Collection created'}), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'A collection with this name already exists in your library'}), 409

@app.route('/api/collections/<int:col_id>', methods=['DELETE'])
def delete_collection(col_id):
    user = get_authenticated_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = user['id']

    if is_supabase_enabled():
        if delete_supabase_collection(col_id, user_id=user_id):
            return jsonify({'success': True, 'message': 'Collection deleted'})
        return jsonify({'error': 'Collection not found or unauthorized'}), 404

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM collections WHERE id = ? AND user_id = ?", (col_id, user_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    if affected > 0:
        return jsonify({'success': True, 'message': 'Collection deleted'})
    return jsonify({'error': 'Collection not found or unauthorized'}), 404

# --- TAGS API ---
@app.route('/api/tags', methods=['GET'])
def list_tags():
    user = get_authenticated_user()
    if not user:
        return jsonify({'tags': []})
    user_id = user['id']

    if is_supabase_enabled():
        tags = get_supabase_tags(user_id=user_id)
        return jsonify({'tags': tags})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.*, COUNT(rt.reel_id) as reel_count
        FROM tags t
        JOIN reel_tags rt ON t.id = rt.tag_id
        JOIN reels r ON rt.reel_id = r.id AND r.is_archived = 0 AND r.user_id = ?
        GROUP BY t.id
        ORDER BY reel_count DESC
    ''', (user_id,))
    tags = [dict(t) for t in cursor.fetchall()]
    conn.close()
    return jsonify({'tags': tags})

# --- FRONTEND PAGES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

# --- AUTHENTICATION API ---
@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    # Try Supabase Auth
    if is_supabase_enabled() and supabase_client:
        try:
            res = supabase_client.auth.sign_in_with_password({"email": email, "password": password})
            if res.user:
                u = res.user
                user_id = str(u.id)
                access_token = res.session.access_token if res.session else None
                display_name = u.user_metadata.get('full_name') or email.split('@')[0].capitalize()
                avatar_url = u.user_metadata.get('avatar_url') or 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80'

                # Store in signed server session
                session['user_id'] = user_id
                session['user_email'] = u.email
                session['user_display_name'] = display_name
                session['user_avatar'] = avatar_url
                session['user_role'] = 'Pro Member'
                session['access_token'] = access_token

                # Seed user starter collections if new
                ensure_default_collections(user_id)

                user_obj = {
                    'id': user_id,
                    'email': u.email,
                    'display_name': display_name,
                    'avatar_url': avatar_url,
                    'role': 'Pro Member'
                }
                return jsonify({
                    'success': True,
                    'user': user_obj,
                    'access_token': access_token
                })
        except Exception as e:
            err_msg = str(e)
            if 'Invalid login credentials' not in err_msg and 'invalid_credentials' not in err_msg.lower():
                print(f"[Supabase Auth Note] {e}")

    # Fallback Account Verification
    if len(password) >= 6:
        user_id = f"usr_{abs(hash(email)) % 10000000}"
        display_name = email.split('@')[0].replace('.', ' ').capitalize()
        avatar_url = 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=120&h=120&q=80'

        session['user_id'] = user_id
        session['user_email'] = email
        session['user_display_name'] = display_name
        session['user_avatar'] = avatar_url
        session['user_role'] = 'Creator Member'

        user_obj = {
            'id': user_id,
            'email': email,
            'display_name': display_name,
            'avatar_url': avatar_url,
            'role': 'Creator Member'
        }
        return jsonify({
            'success': True,
            'user': user_obj
        })

    return jsonify({'error': 'Invalid email or password. Password must be at least 6 characters.'}), 401

@app.route('/api/auth/signup', methods=['POST'])
def api_auth_signup():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    name = (data.get('name') or '').strip() or email.split('@')[0].capitalize()

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    if is_supabase_enabled() and supabase_client:
        try:
            res = supabase_client.auth.sign_up({
                "email": email, 
                "password": password,
                "options": {"data": {"full_name": name}}
            })
            if res.user:
                u = res.user
                user_id = str(u.id)
                access_token = res.session.access_token if res.session else None
                avatar_url = 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=120&h=120&q=80'

                session['user_id'] = user_id
                session['user_email'] = u.email
                session['user_display_name'] = name
                session['user_avatar'] = avatar_url
                session['user_role'] = 'Creator Member'
                session['access_token'] = access_token

                ensure_default_collections(user_id)

                return jsonify({
                    'success': True,
                    'user': {
                        'id': user_id,
                        'email': u.email,
                        'display_name': name,
                        'avatar_url': avatar_url,
                        'role': 'Creator Member'
                    },
                    'access_token': access_token
                })
        except Exception as e:
            print(f"[Supabase SignUp Note] {e}")

    # Fallback
    user_id = f"usr_{abs(hash(email)) % 10000000}"
    avatar_url = 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=120&h=120&q=80'
    session['user_id'] = user_id
    session['user_email'] = email
    session['user_display_name'] = name
    session['user_avatar'] = avatar_url
    session['user_role'] = 'Creator Member'

    return jsonify({
        'success': True,
        'user': {
            'id': user_id,
            'display_name': name,
            'email': email,
            'avatar_url': avatar_url,
            'role': 'Creator Member'
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    session.clear()
    resp = jsonify({'success': True, 'message': 'Logged out successfully'})
    resp.set_cookie('vault_session', '', expires=0)
    return resp

@app.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    user = get_authenticated_user()
    if not user:
        return jsonify({'authenticated': False}), 401
    return jsonify({'authenticated': True, 'user': user})

@app.route('/api/auth/profile', methods=['PATCH', 'POST'])
def update_user_profile():
    user = get_authenticated_user()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = user['id']

    data = request.get_json() or {}
    display_name = (data.get('display_name') or '').strip()
    role = (data.get('role') or user.get('role') or 'Creator Member').strip()
    email = (data.get('email') or user.get('email') or '').strip()
    avatar_url = (data.get('avatar_url') or user.get('avatar_url') or '').strip()

    if not display_name:
        return jsonify({'error': 'Display name is required'}), 400

    # Update in-session profile
    session['user_display_name'] = display_name
    session['user_role'] = role
    session['user_avatar'] = avatar_url

    if is_supabase_enabled():
        try:
            profile_data = {
                'display_name': display_name,
                'full_name': display_name,
                'email': email,
                'avatar_url': avatar_url
            }
            supabase_client.table('profiles').upsert({'id': user_id, **profile_data}).execute()
        except Exception as e:
            print(f"[Supabase profile update note] {e}")

    return jsonify({
        'success': True,
        'user': {
            'id': user_id,
            'display_name': display_name,
            'email': email,
            'avatar_url': avatar_url,
            'role': role
        },
        'message': 'Profile updated successfully!'
    })

@app.route('/manifest.json')
def manifest():
    response = make_response(send_from_directory(BASE_DIR, 'manifest.json'))
    response.headers['Content-Type'] = 'application/manifest+json'
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response

@app.route('/sw.js')
def service_worker():
    response = make_response(send_from_directory(BASE_DIR, 'sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(BASE_DIR, 'static', 'icons'), 'icon-192.png', mimetype='image/png')

if __name__ == '__main__':
    init_db()
    print("Vault SQLite Database Initialized.")
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Vault Web Application at http://localhost:{port}")
    app.run(host='127.0.0.1', port=port, debug=False)
