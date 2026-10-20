import os
import re
import json
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()
from supabase_db import (
    supabase_client, is_supabase_enabled, upload_file_to_supabase,
    get_supabase_reels, get_supabase_reel, insert_supabase_reel,
    update_supabase_reel, delete_supabase_reel, format_supabase_reel,
    get_supabase_collections, insert_supabase_collection, delete_supabase_collection
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
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB limit

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'webm', 'mkv', 'jpg', 'jpeg', 'png', 'webp'}

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

# Initialize Database Schema & Seed Data
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
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        color TEXT DEFAULT '#4F46E5',
        icon TEXT DEFAULT 'folder',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS reels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_url TEXT,
        normalized_url TEXT UNIQUE,
        title TEXT NOT NULL,
        description TEXT,
        creator_username TEXT,
        creator_avatar TEXT,
        thumbnail_url TEXT,
        video_url TEXT,
        media_type TEXT DEFAULT 'video', -- 'video', 'link', 'image'
        save_status TEXT DEFAULT 'saved_video', -- 'saved_video', 'saved_link', 'processing', 'failed'
        duration TEXT DEFAULT '0:30',
        aspect_ratio TEXT DEFAULT '9:16',
        is_favorite INTEGER DEFAULT 0,
        is_watch_later INTEGER DEFAULT 0,
        is_archived INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    # Seed Default User Profile if empty
    cursor.execute("SELECT COUNT(*) as count FROM profiles")
    if cursor.fetchone()['count'] == 0:
        cursor.execute('''
            INSERT INTO profiles (id, display_name, email, avatar_url)
            VALUES (?, ?, ?, ?)
        ''', (
            'usr_vault_pro',
            'Alex Rivera',
            'alex@vaultcreative.design',
            'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=200&h=200&q=80'
        ))

    # Seed Default Collections from Brief
    cursor.execute("SELECT COUNT(*) as count FROM collections")
    if cursor.fetchone()['count'] == 0:
        default_collections = [
            ('Transitions', 'Creative camera & match cut transitions', '#06B6D4', 'wand-2'),
            ('Typography', 'Kinetic, 3D and editorial title animations', '#F59E0B', 'type'),
            ('UI/UX', 'Mobile interactions, glassmorphism & dashboard flows', '#8B5CF6', 'layout'),
            ('Motion Graphics', 'Abstract 3D renders, cyber HUDs, and VFX loops', '#10B981', 'activity'),
            ('Brand Ads', 'High production luxury and commercial reels', '#EC4899', 'badge-percent'),
            ('Cafes', 'Atmospheric B-roll, aesthetic pours, and hospitality', '#D97706', 'coffee'),
            ('Client References', 'Client proposal benchmarks and pitch moodboards', '#3B82F6', 'briefcase')
        ]
        cursor.executemany('''
            INSERT INTO collections (name, description, color, icon)
            VALUES (?, ?, ?, ?)
        ''', default_collections)

    # Seed High-Quality Creative Reels with playable video references
    cursor.execute("SELECT COUNT(*) as count FROM reels")
    if cursor.fetchone()['count'] == 0:
        seed_reels = [
            (
                'https://www.instagram.com/reel/C3_Typography_01/',
                'https://www.instagram.com/reel/C3_Typography_01/',
                'Kinetic Typography & Dynamic Stagger Text In After Effects',
                'Breakdown of the kinetic typography title animation sequence used in the Apple keynote reveal. Notice the letter-by-letter spring physics and optical kerning compensations.',
                '@motion_type_lab',
                'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=100&h=100&q=80',
                'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&h=750&q=80',
                'https://assets.mixkit.co/videos/preview/mixkit-vertical-animation-of-futuristic-lines-and-numbers-41551-large.mp4',
                'video', 'saved_video', '0:24', 1, 0, 0
            ),
            (
                'https://www.instagram.com/reel/C4_UIUX_Glass_02/',
                'https://www.instagram.com/reel/C4_UIUX_Glass_02/',
                'Liquid Glassmorphism 3D Button Hover Interaction',
                'A stunning spatial UI concept showing real-time refractive caustic blur shaders applied to interactive button triggers.',
                '@interface_craft',
                'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=100&h=100&q=80',
                'https://images.unsplash.com/photo-1550745165-9bc0b252726f?auto=format&fit=crop&w=600&h=750&q=80',
                'https://assets.mixkit.co/videos/preview/mixkit-vertical-animation-of-a-futuristic-digital-clock-41550-large.mp4',
                'video', 'saved_video', '0:18', 1, 1, 0
            ),
            (
                'https://www.instagram.com/reel/C5_Transition_Zoom_03/',
                'https://www.instagram.com/reel/C5_Transition_Zoom_03/',
                'Seamless Match Cut Speed Ramp & Lens Blur Transition',
                'How to transition between two contrasting city street scenes using a quick whip pan coupled with motion vector direction blur in DaVinci Resolve.',
                '@cinematic_cuts',
                'https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?auto=format&fit=crop&w=100&h=100&q=80',
                'https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=600&h=750&q=80',
                'https://assets.mixkit.co/videos/preview/mixkit-vertical-view-of-neon-lights-in-a-futuristic-tunnel-41552-large.mp4',
                'video', 'saved_video', '0:15', 0, 1, 0
            ),
            (
                'https://www.instagram.com/reel/C6_MotionGraphics_HUD_04/',
                'https://www.instagram.com/reel/C6_MotionGraphics_HUD_04/',
                'Cyberpunk 3D Holographic HUD Motion Sequence',
                'Complex multi-layered UI tracking with depth passes, chromatic aberration, and particle emitters rendered in Blender Cycles.',
                '@future_motion',
                'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=100&h=100&q=80',
                'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=600&h=750&q=80',
                'https://assets.mixkit.co/videos/preview/mixkit-vertical-projection-of-neon-geometric-figures-41555-large.mp4',
                'video', 'saved_video', '0:32', 1, 0, 0
            ),
            (
                'https://www.instagram.com/reel/C7_BrandAd_Luxury_05/',
                'https://www.instagram.com/reel/C7_BrandAd_Luxury_05/',
                'Luxury Minimalist Fragrance Commercial Color Grade',
                'Warm Kodak 2383 print emulation applied over Alexa Mini LF Arri LogC footage. Minimal camera movement with sound design driving the emotional beat.',
                '@director_ad_studio',
                'https://images.unsplash.com/photo-1522075469751-3a6694fb2f61?auto=format&fit=crop&w=100&h=100&q=80',
                'https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=600&h=750&q=80',
                'https://assets.mixkit.co/videos/preview/mixkit-vertical-lights-and-smoke-in-the-dark-41554-large.mp4',
                'video', 'saved_video', '0:45', 1, 0, 0
            ),
            (
                'https://www.instagram.com/reel/C8_Cafe_BRoll_06/',
                'https://www.instagram.com/reel/C8_Cafe_BRoll_06/',
                'Atmospheric Japanese Café Pour Over Slow Motion 120fps',
                'Natural morning light, steam diffusion filter (1/4 Black Pro Mist), and tactile sound design. Perfect reference for café clients.',
                '@tokyo_coffees',
                'https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=100&h=100&q=80',
                'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=600&h=750&q=80',
                'https://assets.mixkit.co/videos/preview/mixkit-vertical-animation-of-futuristic-lines-and-numbers-41551-large.mp4',
                'video', 'saved_video', '0:22', 0, 0, 0
            ),
            (
                'https://www.instagram.com/reel/C9_ClientRef_Fintech_07/',
                'https://www.instagram.com/reel/C9_ClientRef_Fintech_07/',
                'Fintech Mobile Card Swipe & Micro-Interactions',
                'Interactive credit card 3D tilt gesture based on device gyroscope. Smooth 60fps springs using Framer Motion physics.',
                '@fintech_design',
                'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=100&h=100&q=80',
                'https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=600&h=750&q=80',
                'https://assets.mixkit.co/videos/preview/mixkit-vertical-animation-of-a-futuristic-digital-clock-41550-large.mp4',
                'video', 'saved_link', '0:19', 0, 1, 0
            )
        ]

        cursor.executemany('''
            INSERT INTO reels (
                original_url, normalized_url, title, description,
                creator_username, creator_avatar, thumbnail_url, video_url,
                media_type, save_status, duration, is_favorite, is_watch_later, is_archived
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', seed_reels)

        # Seed tags
        tags = ['Kinetic', 'AfterEffects', 'UIUX', 'Transitions', 'DaVinci', 'Commercial', 'Minimal', 'Blender', 'Coffee', 'Fintech']
        cursor.executemany("INSERT OR IGNORE INTO tags (name) VALUES (?)", [(t,) for t in tags])

        # Map reel collections & tags
        mappings = [
            (1, 2, ['Kinetic', 'AfterEffects']),    # Reel 1 -> Typography
            (2, 3, ['UIUX', 'Minimal']),           # Reel 2 -> UI/UX
            (3, 1, ['Transitions', 'DaVinci']),    # Reel 3 -> Transitions
            (4, 4, ['Blender']),                   # Reel 4 -> Motion Graphics
            (5, 5, ['Commercial', 'Minimal']),     # Reel 5 -> Brand Ads
            (6, 6, ['Coffee', 'Minimal']),         # Reel 6 -> Cafes
            (7, 7, ['Fintech', 'UIUX']),           # Reel 7 -> Client References
        ]

        for reel_id, col_id, reel_tag_names in mappings:
            cursor.execute("INSERT OR IGNORE INTO reel_collections (reel_id, collection_id) VALUES (?, ?)", (reel_id, col_id))
            for tag_name in reel_tag_names:
                cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
                t_row = cursor.fetchone()
                if t_row:
                    cursor.execute("INSERT OR IGNORE INTO reel_tags (reel_id, tag_id) VALUES (?, ?)", (reel_id, t_row['id']))

    conn.commit()
    conn.close()

# Helper: Format Reel response with collections and tags
def format_reel(row, conn):
    reel_id = row['id']
    cursor = conn.cursor()

    # Get collections
    cursor.execute('''
        SELECT c.id, c.name, c.color, c.icon 
        FROM collections c
        JOIN reel_collections rc ON c.id = rc.collection_id
        WHERE rc.reel_id = ?
    ''', (reel_id,))
    collections = [dict(c) for c in cursor.fetchall()]

    # Get tags
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

# --- API ROUTES ---

@app.route('/api/reels', methods=['GET'])
def list_reels():
    collection_id = request.args.get('collection')
    tag_name = request.args.get('tag')
    media_type = request.args.get('type')  # 'all', 'video', 'link'
    search = request.args.get('search', '').strip()
    status = request.args.get('status') # 'all', 'favorite', 'watch_later', 'archived'
    sort = request.args.get('sort', 'latest') # 'latest', 'oldest', 'title'

    # Delegate to Supabase PostgreSQL when enabled
    if is_supabase_enabled():
        supa_reels = get_supabase_reels(collection_id=collection_id, media_type=media_type, status=status, search=search, sort=sort)
        if supa_reels is not None:
            return jsonify({'reels': supa_reels, 'count': len(supa_reels)})

    conn = get_db()
    cursor = conn.cursor()

    query = '''
        SELECT DISTINCT r.* 
        FROM reels r
        LEFT JOIN reel_collections rc ON r.id = rc.reel_id
        LEFT JOIN reel_tags rt ON r.id = rt.reel_id
        LEFT JOIN tags t ON rt.tag_id = t.id
        WHERE 1=1
    '''
    params = []

    # Filter by Archive state
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
    if is_supabase_enabled():
        supa_reel = get_supabase_reel(reel_id)
        if supa_reel:
            return jsonify({'reel': supa_reel})
        return jsonify({'error': 'Reel not found'}), 404

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reels WHERE id = ?", (reel_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Reel not found'}), 404

    reel = format_reel(row, conn)
    conn.close()
    return jsonify({'reel': reel})

def extract_reel_media_info(url):
    """Extracts direct video MP4 URL, thumbnail, creator, and title via yt-dlp."""
    if not url:
        return None
    try:
        import yt_dlp
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 10
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')
            if not video_url and 'formats' in info and info['formats']:
                for fmt in reversed(info['formats']):
                    if fmt.get('url') and (fmt.get('vcodec') != 'none' or 'mp4' in fmt.get('ext', '')):
                        video_url = fmt['url']
                        break
                if not video_url:
                    video_url = info['formats'][-1].get('url')

            thumb = info.get('thumbnail')
            title = info.get('title')
            uploader = info.get('uploader') or info.get('channel')
            creator_handle = f"@{uploader}" if uploader and not uploader.startswith('@') else (uploader or '@instagram_creator')
            duration_sec = info.get('duration')
            duration_str = f"0:{int(duration_sec):02d}" if duration_sec else "0:30"

            return {
                'video_url': video_url,
                'thumbnail_url': thumb,
                'title': title,
                'creator_username': creator_handle,
                'description': info.get('description'),
                'duration': duration_str
            }
    except Exception as e:
        print(f"[Media extraction note] {e}")
        return None

@app.route('/api/reels/<int:reel_id>/video', methods=['GET'])
def get_reel_video_stream(reel_id):
    """Returns direct video stream or redirects to resolved MP4 URL."""
    target_reel = None
    if is_supabase_enabled():
        target_reel = get_supabase_reel(reel_id)
    else:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reels WHERE id = ?", (reel_id,))
        row = cursor.fetchone()
        if row:
            target_reel = dict(row)
        conn.close()

    if not target_reel:
        return jsonify({'error': 'Reel not found'}), 404

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
                    })
                else:
                    conn = get_db()
                    conn.execute("UPDATE reels SET video_url = ?, thumbnail_url = ?, save_status = 'saved_video' WHERE id = ?", (video_url, new_thumb, reel_id))
                    conn.commit()
                    conn.close()

    if video_url:
        return redirect(video_url, code=302)

    return jsonify({'error': 'Video stream not available for this reel'}), 404

@app.route('/api/parse-url', methods=['POST'])
def parse_instagram_url():
    """Validates Instagram Reel URL, checks duplicates, and extracts direct video."""
    data = request.get_json() or {}
    raw_url = (data.get('url') or '').strip()

    if not raw_url:
        return jsonify({'error': 'URL is required'}), 400

    normalized_url, shortcode = normalize_instagram_url(raw_url)
    if not shortcode and not ('instagram.com' in raw_url):
        return jsonify({'error': 'Please provide a valid Instagram Reel or Post link'}), 400

    # Supabase duplicate check
    if is_supabase_enabled():
        try:
            supa_res = supabase_client.table('reels').select('*, reel_collections(collection_id, collections(*)), reel_tags(tag_id, tags(*))').or_(f"normalized_url.eq.{normalized_url},original_url.eq.{raw_url}").execute().data
            if supa_res:
                reel = format_supabase_reel(supa_res[0])
                return jsonify({
                    'duplicate': True,
                    'message': 'This Reel is already saved in your Vault!',
                    'existing_reel': reel
                })
        except Exception as e:
            print(f"[Supabase duplicate check] {e}")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reels WHERE normalized_url = ? OR original_url = ?", (normalized_url, raw_url))
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

    # Default metadata
    creator_handle = '@instagram_creator'
    title = f"Instagram Creative Reference ({shortcode or 'Reel'})"
    description = "Saved Instagram Reel inspiration. Metadata preserved from shared link."
    thumbnail = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&h=750&q=80"
    extracted_video_url = None
    duration = '0:30'

    # Direct video stream & metadata extraction via yt-dlp
    media_info = extract_reel_media_info(raw_url) or extract_reel_media_info(normalized_url)
    if media_info:
        title = media_info.get('title') or title
        creator_handle = media_info.get('creator_username') or creator_handle
        thumbnail = media_info.get('thumbnail_url') or thumbnail
        extracted_video_url = media_info.get('video_url')
        description = media_info.get('description') or description
        duration = media_info.get('duration') or duration

    return jsonify({
        'duplicate': False,
        'normalized_url': normalized_url,
        'shortcode': shortcode,
        'title': title,
        'creator_username': creator_handle,
        'description': description,
        'thumbnail_url': thumbnail,
        'video_url': extracted_video_url,
        'duration': duration,
        'save_status': 'saved_video' if extracted_video_url else 'saved_link'
    })

@app.route('/api/reels', methods=['POST'])
def create_reel():
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

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    # Auto-extract video stream if not present
    if not video_url and original_url:
        media_info = extract_reel_media_info(original_url)
        if media_info and media_info.get('video_url'):
            video_url = media_info['video_url']
            if not thumbnail_url and media_info.get('thumbnail_url'):
                thumbnail_url = media_info['thumbnail_url']

    save_status = data.get('save_status') or ('saved_video' if video_url else 'saved_link')
    normalized_url, _ = normalize_instagram_url(original_url) if original_url else (None, None)

    # Delegate to Supabase if active
    if is_supabase_enabled():
        supa_data = {
            'original_url': original_url or 'https://instagram.com/reel/upload',
            'normalized_url': normalized_url or f"manual_{int(datetime.utcnow().timestamp())}",
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
        new_supa_reel = insert_supabase_reel(supa_data, collection_id=collection_id, tags=tags_list)
        if new_supa_reel:
            return jsonify({'reel': new_supa_reel, 'message': 'Reel saved successfully to Supabase!'}), 201

    conn = get_db()
    cursor = conn.cursor()

    # Duplicate check
    if normalized_url:
        cursor.execute("SELECT id FROM reels WHERE normalized_url = ?", (normalized_url,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return jsonify({'error': 'This Reel already exists in your library'}), 409

    if not thumbnail_url:
        thumbnail_url = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&h=750&q=80"

    cursor.execute('''
        INSERT INTO reels (
            original_url, normalized_url, title, description,
            creator_username, creator_avatar, thumbnail_url, video_url,
            media_type, save_status, duration
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        original_url,
        normalized_url or f"manual_{datetime.utcnow().timestamp()}",
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

    cursor.execute("SELECT * FROM reels WHERE id = ?", (reel_id,))
    new_reel = format_reel(cursor.fetchone(), conn)
    conn.close()
    return jsonify({'reel': new_reel, 'message': 'Reel saved successfully!'}), 201

@app.route('/api/reels/<int:reel_id>', methods=['PATCH'])
def update_reel(reel_id):
    data = request.get_json() or {}
    
    # Allowed fields
    updatable = ['title', 'description', 'creator_username', 'is_favorite', 'is_watch_later', 'is_archived', 'save_status']
    updates = {k: data[k] for k in updatable if k in data}

    if is_supabase_enabled():
        supa_updated = update_supabase_reel(
            reel_id, 
            updates, 
            collection_id=data.get('collection_id'), 
            tags=data.get('tags')
        )
        if supa_updated:
            return jsonify({'reel': supa_updated, 'message': 'Reel updated successfully in Supabase'})

    conn = get_db()
    cursor = conn.cursor()

    sql_updates = []
    values = []

    for key, val in updates.items():
        sql_updates.append(f"{key} = ?")
        values.append(val)

    if sql_updates:
        values.append(datetime.utcnow())
        values.append(reel_id)
        cursor.execute(f"UPDATE reels SET {', '.join(sql_updates)}, updated_at = ? WHERE id = ?", values)

    # Update collection if passed
    if 'collection_id' in data:
        col_id = data['collection_id']
        cursor.execute("DELETE FROM reel_collections WHERE reel_id = ?", (reel_id,))
        if col_id:
            cursor.execute("INSERT INTO reel_collections (reel_id, collection_id) VALUES (?, ?)", (reel_id, int(col_id)))

    # Update tags if passed
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
    cursor.execute("SELECT * FROM reels WHERE id = ?", (reel_id,))
    updated = format_reel(cursor.fetchone(), conn)
    conn.close()
    return jsonify({'reel': updated, 'message': 'Reel updated successfully'})

@app.route('/api/reels/<int:reel_id>', methods=['DELETE'])
def delete_reel(reel_id):
    if is_supabase_enabled():
        if delete_supabase_reel(reel_id):
            return jsonify({'success': True, 'message': 'Reel removed from Supabase'})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reels WHERE id = ?", (reel_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Reel removed from Vault'})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Direct video upload supporting MP4, MOV, WebM, up to 500MB."""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400

    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{int(datetime.utcnow().timestamp())}_{file.filename}")
        
        # Check if Supabase Storage is active
        video_url = None
        if is_supabase_enabled():
            try:
                file_bytes = file.read()
                content_type = file.content_type or 'video/mp4'
                video_url = upload_file_to_supabase(file_bytes, filename, content_type)
            except Exception as e:
                print(f"[Supabase Upload Fallback] {e}")

        # Local storage fallback
        if not video_url:
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.seek(0)
            file.save(save_path)
            video_url = f"/uploads/{filename}"

        return jsonify({
            'success': True,
            'filename': filename,
            'video_url': video_url,
            'storage': 'supabase' if is_supabase_enabled() else 'local',
            'save_status': 'saved_video',
            'message': 'Video uploaded securely to Vault Storage.'
        })

    return jsonify({'error': 'File format not supported. Use MP4, MOV, or WebM.'}), 400

@app.route('/api/status', methods=['GET'])
def get_system_status():
    """Returns deployment environment and Supabase connection state."""
    supabase_active = is_supabase_enabled()
    is_vercel = bool(os.environ.get('VERCEL')) or bool(os.environ.get('VERCEL_ENV'))
    return jsonify({
        'status': 'online',
        'database': 'Supabase PostgreSQL' if supabase_active else 'SQLite (Local)',
        'storage': 'Supabase Storage (vault-media)' if supabase_active else 'Local Storage',
        'platform': 'Vercel Serverless' if is_vercel else 'Localhost Environment',
        'supabase_configured': supabase_active,
        'vercel_environment': is_vercel
    })

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Collections API
@app.route('/api/collections', methods=['GET'])
def list_collections():
    if is_supabase_enabled():
        supa_cols = get_supabase_collections()
        if supa_cols is not None:
            return jsonify({'collections': supa_cols})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.*, COUNT(rc.reel_id) as reel_count 
        FROM collections c
        LEFT JOIN reel_collections rc ON c.id = rc.collection_id
        LEFT JOIN reels r ON rc.reel_id = r.id AND r.is_archived = 0
        GROUP BY c.id
        ORDER BY c.name ASC
    ''')
    collections = [dict(c) for c in cursor.fetchall()]
    conn.close()
    return jsonify({'collections': collections})

@app.route('/api/collections', methods=['POST'])
def create_collection():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    color = (data.get('color') or '#4F46E5').strip()
    icon = (data.get('icon') or 'folder').strip()

    if not name:
        return jsonify({'error': 'Collection name is required'}), 400

    if is_supabase_enabled():
        new_supa_col = insert_supabase_collection(name, description, color, icon)
        if new_supa_col:
            return jsonify({'collection': new_supa_col, 'message': 'Collection created'}), 201

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO collections (name, description, color, icon)
            VALUES (?, ?, ?, ?)
        ''', (name, description, color, icon))
        conn.commit()
        col_id = cursor.lastrowid
        cursor.execute("SELECT *, 0 as reel_count FROM collections WHERE id = ?", (col_id,))
        new_col = dict(cursor.fetchone())
        conn.close()
        return jsonify({'collection': new_col, 'message': 'Collection created'}), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'A collection with this name already exists'}), 409

@app.route('/api/collections/<int:col_id>', methods=['DELETE'])
def delete_collection(col_id):
    if is_supabase_enabled():
        if delete_supabase_collection(col_id):
            return jsonify({'success': True, 'message': 'Collection deleted'})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM collections WHERE id = ?", (col_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Collection deleted'})

# Tags API
@app.route('/api/tags', methods=['GET'])
def list_tags():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.*, COUNT(rt.reel_id) as reel_count
        FROM tags t
        JOIN reel_tags rt ON t.id = rt.tag_id
        JOIN reels r ON rt.reel_id = r.id AND r.is_archived = 0
        GROUP BY t.id
        ORDER BY reel_count DESC
    ''')
    tags = [dict(t) for t in cursor.fetchall()]
    conn.close()
    return jsonify({'tags': tags})

# Frontend Web Application Route
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    # Try Supabase Auth
    if is_supabase_enabled():
        try:
            res = supabase_client.auth.sign_in_with_password({"email": email, "password": password})
            if res.user:
                return jsonify({
                    'success': True,
                    'user': {
                        'id': res.user.id,
                        'email': res.user.email,
                        'display_name': res.user.user_metadata.get('full_name') or email.split('@')[0].capitalize(),
                        'avatar_url': res.user.user_metadata.get('avatar_url') or 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80',
                        'role': 'Pro Member'
                    }
                })
        except Exception as e:
            err_msg = str(e)
            if 'Invalid login credentials' not in err_msg and 'invalid_credentials' not in err_msg.lower():
                print(f"[Supabase Auth Note] {e}")

    # Fallback / Demo Account Support
    if email == 'alex@vaultcreative.design' or 'demo' in email:
        return jsonify({
            'success': True,
            'user': {
                'id': 'usr_vault_pro',
                'display_name': 'Alex Rivera',
                'email': 'alex@vaultcreative.design',
                'avatar_url': 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80',
                'role': 'Pro Creator'
            }
        })
    elif len(password) >= 6:
        return jsonify({
            'success': True,
            'user': {
                'id': f"usr_{abs(hash(email)) % 1000000}",
                'display_name': email.split('@')[0].replace('.', ' ').capitalize(),
                'email': email,
                'avatar_url': 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=120&h=120&q=80',
                'role': 'Creator Member'
            }
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

    if is_supabase_enabled():
        try:
            res = supabase_client.auth.sign_up({
                "email": email, 
                "password": password,
                "options": {"data": {"full_name": name}}
            })
            if res.user:
                return jsonify({
                    'success': True,
                    'user': {
                        'id': res.user.id,
                        'email': res.user.email,
                        'display_name': name,
                        'avatar_url': 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=120&h=120&q=80',
                        'role': 'Creator Member'
                    }
                })
        except Exception as e:
            print(f"[Supabase SignUp Note] {e}")

    return jsonify({
        'success': True,
        'user': {
            'id': f"usr_{abs(hash(email)) % 1000000}",
            'display_name': name,
            'email': email,
            'avatar_url': 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=120&h=120&q=80',
            'role': 'Creator Member'
        }
    })

@app.route('/api/auth/demo', methods=['POST'])
def api_auth_demo():
    return jsonify({
        'success': True,
        'user': {
            'id': 'usr_vault_pro',
            'display_name': 'Alex Rivera',
            'email': 'alex@vaultcreative.design',
            'avatar_url': 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80',
            'role': 'Pro Creator'
        }
    })

@app.route('/manifest.json')
def manifest():
    return send_from_directory(BASE_DIR, 'manifest.json')

if __name__ == '__main__':
    init_db()
    print("Vault SQLite Database Initialized.")
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Vault Web Application at http://localhost:{port}")
    app.run(host='127.0.0.1', port=port, debug=False)
