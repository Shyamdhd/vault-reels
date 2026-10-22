import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SUPABASE_URL = "https://lrjhhtkbwztzfcuskrif.supabase.co"
DEFAULT_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxyamhodGtid3p0emZjdXNrcmlmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg4NTE2MDQsImV4cCI6MjEwNDQyNzYwNH0.IPOhuBm6VWFcnkQ3EQThS4soTZRDcEBgwLDTorgxSF8"
DEFAULT_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxyamhodGtid3p0emZjdXNrcmlmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODg1MTYwNCwiZXhwIjoyMTA0NDI3NjA0fQ.pxDgAg_jM_PWoHYoLhUwEQssPbqNFBEOWVatAS40RMs"

SUPABASE_URL = os.environ.get("SUPABASE_URL") or DEFAULT_SUPABASE_URL
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY") or DEFAULT_SUPABASE_KEY
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or DEFAULT_SERVICE_ROLE_KEY

supabase_client = None
supabase_admin = None

if SUPABASE_URL and SUPABASE_KEY and "your-project" not in SUPABASE_URL:
    try:
        from supabase import create_client, Client
        supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"[Supabase] Connected to Supabase Project: {SUPABASE_URL}")
    except Exception as e:
        print(f"[Supabase] Client connection warning: {e}")
        supabase_client = None

if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and "your-project" not in SUPABASE_URL:
    try:
        from supabase import create_client, Client
        supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        print(f"[Supabase] Initialized Supabase Admin Service Client")
    except Exception as e:
        print(f"[Supabase] Admin connection warning: {e}")
        supabase_admin = None

def is_supabase_enabled():
    return (supabase_admin is not None) or (supabase_client is not None)

def get_db():
    """Returns the privileged admin client for server-verified operations."""
    return supabase_admin or supabase_client

# --- Supabase Storage Helper ---
def upload_file_to_supabase(file_bytes, filename, content_type="video/mp4", user_id=None):
    """Uploads media file directly to Supabase Storage bucket 'vault-media' under user's directory."""
    client = get_db()
    if not client:
        return None
    try:
        bucket = "vault-media"
        path = f"uploads/{user_id}/{filename}" if user_id else f"uploads/{filename}"
        client.storage.from_(bucket).upload(path, file_bytes, {"content-type": content_type})
        public_url = client.storage.from_(bucket).get_public_url(path)
        return public_url
    except Exception as e:
        print(f"[Supabase Storage Error] {e}")
        return None

# --- Supabase Database Helpers (Strict Multi-Tenant Isolation) ---

def format_supabase_reel(r):
    """Normalize Supabase joined record into standard reel object."""
    if not r:
        return None
    collections = []
    if 'reel_collections' in r and r['reel_collections']:
        for rc in r['reel_collections']:
            if isinstance(rc, dict) and 'collections' in rc and rc['collections']:
                collections.append(rc['collections'])

    tags = []
    if 'reel_tags' in r and r['reel_tags']:
        for rt in r['reel_tags']:
            if isinstance(rt, dict) and 'tags' in rt and rt['tags']:
                tags.append(rt['tags'])

    clean_reel = dict(r)
    clean_reel.pop('reel_collections', None)
    clean_reel.pop('reel_tags', None)
    clean_reel['collections'] = collections
    clean_reel['tags'] = tags
    clean_reel['primary_collection'] = collections[0] if collections else None
    return clean_reel

def get_supabase_reels(user_id, collection_id=None, media_type=None, status=None, search=None, sort='latest'):
    """Fetch reels strictly owned by the authenticated user_id."""
    if not is_supabase_enabled() or not user_id:
        return []
    try:
        client = get_db()
        # Enforce strict user_id isolation
        q = client.table('reels').select('*, reel_collections(collection_id, collections(*)), reel_tags(tag_id, tags(*))').eq('user_id', user_id)
        
        if status == 'archived':
            q = q.eq('is_archived', True)
        else:
            q = q.eq('is_archived', False)

        if status == 'favorite':
            q = q.eq('is_favorite', True)
        elif status == 'watch_later':
            q = q.eq('is_watch_later', True)

        res = q.execute().data or []
        reels = [format_supabase_reel(r) for r in res if r]

        if media_type:
            if media_type == 'reel':
                reels = [r for r in reels if (r.get('media_type') in ['reel', 'video'] or '/reel/' in (r.get('original_url') or '') or '/reels/' in (r.get('original_url') or ''))]
            elif media_type == 'post':
                reels = [r for r in reels if (r.get('media_type') in ['post', 'image'] or '/p/' in (r.get('original_url') or ''))]
            elif media_type in ['video', 'link', 'image']:
                reels = [r for r in reels if r.get('media_type') == media_type]

        # In-memory filter for collection & search
        if collection_id and collection_id != 'all':
            try:
                c_id = int(collection_id)
                reels = [r for r in reels if any(c.get('id') == c_id for c in r.get('collections', []))]
            except (ValueError, TypeError):
                pass

        if search:
            kw = search.lower().strip()
            reels = [
                r for r in reels if (
                    kw in r.get('title', '').lower() or
                    kw in (r.get('description') or '').lower() or
                    kw in (r.get('creator_username') or '').lower() or
                    any(kw in t.get('name', '').lower() for t in r.get('tags', []))
                )
            ]

        return reels
    except Exception as e:
        print(f"[Supabase get_reels Error] {e}")
        return []

def get_supabase_reel(reel_id, user_id):
    """Retrieve single reel with ownership verification."""
    if not is_supabase_enabled() or not user_id:
        return None
    try:
        client = get_db()
        res = client.table('reels').select('*, reel_collections(collection_id, collections(*)), reel_tags(tag_id, tags(*))').eq('id', reel_id).eq('user_id', user_id).execute().data
        if res:
            return format_supabase_reel(res[0])
        return None
    except Exception as e:
        print(f"[Supabase get_reel Error] {e}")
        return None

def check_supabase_duplicate_reel(user_id, normalized_url, original_url=None):
    """Check for duplicates strictly within the authenticated user's account."""
    if not is_supabase_enabled() or not user_id:
        return None
    try:
        client = get_db()
        q = client.table('reels').select('*, reel_collections(collection_id, collections(*)), reel_tags(tag_id, tags(*))').eq('user_id', user_id)
        if original_url and normalized_url:
            q = q.or_(f"normalized_url.eq.{normalized_url},original_url.eq.{original_url}")
        elif normalized_url:
            q = q.eq('normalized_url', normalized_url)
        else:
            q = q.eq('original_url', original_url)
        
        res = q.execute().data
        if res:
            return format_supabase_reel(res[0])
        return None
    except Exception as e:
        print(f"[Supabase duplicate check error] {e}")
        return None

def insert_supabase_reel(reel_data, collection_id=None, tags=None, user_id=None):
    """Insert reel strictly bound to user_id."""
    if not is_supabase_enabled() or not user_id:
        return None
    try:
        client = get_db()
        # Enforce user_id
        reel_data['user_id'] = user_id

        res = client.table('reels').insert(reel_data).execute().data
        if not res:
            return None
        new_reel = res[0]
        reel_id = new_reel['id']

        # Verify collection ownership if specified
        if collection_id:
            col_check = client.table('collections').select('id').eq('id', int(collection_id)).eq('user_id', user_id).execute().data
            if col_check:
                client.table('reel_collections').insert({
                    'reel_id': reel_id,
                    'collection_id': int(collection_id)
                }).execute()

        if tags:
            for tag_name in tags:
                clean_tag = tag_name.strip().lstrip('#')
                if clean_tag:
                    client.table('tags').upsert({'name': clean_tag}, on_conflict='name').execute()
                    tag_row = client.table('tags').select('id').eq('name', clean_tag).execute().data
                    if tag_row:
                        client.table('reel_tags').insert({
                            'reel_id': reel_id,
                            'tag_id': tag_row[0]['id']
                        }).execute()

        return get_supabase_reel(reel_id, user_id)
    except Exception as e:
        print(f"[Supabase insert_reel Error] {e}")
        return None

def update_supabase_reel(reel_id, updates, collection_id=None, tags=None, user_id=None):
    """Update reel with ownership verification."""
    if not is_supabase_enabled() or not user_id:
        return None
    try:
        client = get_db()
        # Verify ownership first
        existing = client.table('reels').select('id').eq('id', reel_id).eq('user_id', user_id).execute().data
        if not existing:
            return None

        # Disallow tampering with user_id
        updates.pop('user_id', None)

        if updates:
            client.table('reels').update(updates).eq('id', reel_id).eq('user_id', user_id).execute()

        if collection_id is not None:
            client.table('reel_collections').delete().eq('reel_id', reel_id).execute()
            if collection_id:
                col_check = client.table('collections').select('id').eq('id', int(collection_id)).eq('user_id', user_id).execute().data
                if col_check:
                    client.table('reel_collections').insert({
                        'reel_id': reel_id,
                        'collection_id': int(collection_id)
                    }).execute()

        if tags is not None and isinstance(tags, list):
            client.table('reel_tags').delete().eq('reel_id', reel_id).execute()
            for tag_name in tags:
                clean_tag = tag_name.strip().lstrip('#')
                if clean_tag:
                    client.table('tags').upsert({'name': clean_tag}, on_conflict='name').execute()
                    tag_row = client.table('tags').select('id').eq('name', clean_tag).execute().data
                    if tag_row:
                        client.table('reel_tags').insert({
                            'reel_id': reel_id,
                            'tag_id': tag_row[0]['id']
                        }).execute()

        return get_supabase_reel(reel_id, user_id)
    except Exception as e:
        print(f"[Supabase update_reel Error] {e}")
        return None

def delete_supabase_reel(reel_id, user_id=None):
    """Delete reel with ownership verification."""
    if not is_supabase_enabled() or not user_id:
        return False
    try:
        client = get_db()
        res = client.table('reels').delete().eq('id', reel_id).eq('user_id', user_id).execute().data
        return bool(res)
    except Exception as e:
        print(f"[Supabase delete_reel Error] {e}")
        return False

def get_supabase_collections(user_id=None):
    """Fetch collections strictly owned by user_id and count only user's reels."""
    if not is_supabase_enabled() or not user_id:
        return []
    try:
        client = get_db()
        cols = client.table('collections').select('*').eq('user_id', user_id).order('name').execute().data or []
        for c in cols:
            # Count active reels owned by this user
            res = client.table('reel_collections').select('reels!inner(user_id, is_archived)', count='exact').eq('collection_id', c['id']).eq('reels.user_id', user_id).eq('reels.is_archived', False).execute()
            c['reel_count'] = res.count or 0
        return cols
    except Exception as e:
        print(f"[Supabase get_collections Error] {e}")
        return []

def ensure_default_collections(user_id):
    """Seed starter collections for a user if they have none."""
    if not is_supabase_enabled() or not user_id:
        return
    try:
        client = get_db()
        existing = client.table('collections').select('id').eq('user_id', user_id).execute().data
        if not existing:
            starter_cols = [
                {'name': 'Transitions', 'description': 'Match cuts, zooms, whip pans', 'color': '#7D53FF', 'icon': 'sparkles', 'user_id': user_id},
                {'name': 'Typography', 'description': 'Kinetic text, titles, subtitles', 'color': '#8B5CF6', 'icon': 'type', 'user_id': user_id},
                {'name': 'UI/UX', 'description': 'App walkthroughs, interactions', 'color': '#EC4899', 'icon': 'smartphone', 'user_id': user_id},
                {'name': 'Motion Graphics', 'description': '3D animations, abstract loops', 'color': '#F59E0B', 'icon': 'film', 'user_id': user_id}
            ]
            client.table('collections').insert(starter_cols).execute()
    except Exception as e:
        print(f"[Supabase ensure_default_collections note] {e}")

def insert_supabase_collection(name, description, color, icon, user_id=None):
    """Insert collection bound strictly to user_id."""
    if not is_supabase_enabled() or not user_id:
        return None
    try:
        client = get_db()
        res = client.table('collections').insert({
            'name': name,
            'description': description,
            'color': color,
            'icon': icon,
            'user_id': user_id
        }).execute().data
        if res:
            res[0]['reel_count'] = 0
            return res[0]
        return None
    except Exception as e:
        print(f"[Supabase insert_collection Error] {e}")
        return None

def delete_supabase_collection(col_id, user_id=None):
    """Delete collection with ownership verification."""
    if not is_supabase_enabled() or not user_id:
        return False
    try:
        client = get_db()
        res = client.table('collections').delete().eq('id', col_id).eq('user_id', user_id).execute().data
        return bool(res)
    except Exception as e:
        print(f"[Supabase delete_collection Error] {e}")
        return False

def get_supabase_tags(user_id=None):
    """Get tags used in reels owned by user_id."""
    if not is_supabase_enabled() or not user_id:
        return []
    try:
        client = get_db()
        # Fetch tags through user's reels
        res = client.table('reel_tags').select('tags(id, name), reels!inner(user_id)').eq('reels.user_id', user_id).execute().data or []
        seen = set()
        user_tags = []
        for r in res:
            t = r.get('tags')
            if t and t.get('name') and t['name'] not in seen:
                seen.add(t['name'])
                user_tags.append(t)
        return user_tags
    except Exception as e:
        print(f"[Supabase get_tags Error] {e}")
        return []
