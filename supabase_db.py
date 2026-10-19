import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase_client = None

if SUPABASE_URL and SUPABASE_KEY and "your-project" not in SUPABASE_URL:
    try:
        from supabase import create_client, Client
        supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"[Supabase] Connected to Supabase Project: {SUPABASE_URL}")
    except Exception as e:
        print(f"[Supabase] Connection warning: {e}")
        supabase_client = None
else:
    print("[Supabase] SUPABASE_URL / SUPABASE_KEY not detected or placeholder. Falling back to SQLite local database.")

def is_supabase_enabled():
    return supabase_client is not None

# --- Supabase Storage Helper ---
def upload_file_to_supabase(file_bytes, filename, content_type="video/mp4"):
    """Uploads media file directly to Supabase Storage bucket 'vault-media'."""
    if not is_supabase_enabled():
        return None
    try:
        bucket = "vault-media"
        path = f"uploads/{filename}"
        supabase_client.storage.from_(bucket).upload(path, file_bytes, {"content-type": content_type})
        public_url = supabase_client.storage.from_(bucket).get_public_url(path)
        return public_url
    except Exception as e:
        print(f"[Supabase Storage Error] {e}")
        return None

# --- Supabase Database Helpers ---

def format_supabase_reel(r):
    """Normalize Supabase joined record into standard reel object."""
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

def get_supabase_reels(collection_id=None, media_type=None, status=None, search=None, sort='latest'):
    if not is_supabase_enabled():
        return None
    try:
        q = supabase_client.table('reels').select('*, reel_collections(collection_id, collections(*)), reel_tags(tag_id, tags(*))')
        
        if status == 'archived':
            q = q.eq('is_archived', True)
        else:
            q = q.eq('is_archived', False)

        if status == 'favorite':
            q = q.eq('is_favorite', True)
        elif status == 'watch_later':
            q = q.eq('is_watch_later', True)

        if media_type and media_type in ['video', 'link', 'image']:
            q = q.eq('media_type', media_type)

        if sort == 'oldest':
            q = q.order('created_at', desc=False)
        elif sort == 'title':
            q = q.order('title', desc=False)
        else:
            q = q.order('created_at', desc=True)

        res = q.execute().data
        reels = [format_supabase_reel(r) for r in res]

        # In-memory filter for collection & search (fast & exact)
        if collection_id and collection_id != 'all':
            c_id = int(collection_id)
            reels = [r for r in reels if any(c['id'] == c_id for c in r.get('collections', []))]

        if search:
            kw = search.lower()
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
        return None

def get_supabase_reel(reel_id):
    if not is_supabase_enabled():
        return None
    try:
        res = supabase_client.table('reels').select('*, reel_collections(collection_id, collections(*)), reel_tags(tag_id, tags(*))').eq('id', reel_id).execute().data
        if res:
            return format_supabase_reel(res[0])
        return None
    except Exception as e:
        print(f"[Supabase get_reel Error] {e}")
        return None

def insert_supabase_reel(reel_data, collection_id=None, tags=None):
    if not is_supabase_enabled():
        return None
    try:
        res = supabase_client.table('reels').insert(reel_data).execute().data
        if not res:
            return None
        new_reel = res[0]
        reel_id = new_reel['id']

        if collection_id:
            supabase_client.table('reel_collections').insert({
                'reel_id': reel_id,
                'collection_id': int(collection_id)
            }).execute()

        if tags:
            for tag_name in tags:
                clean_tag = tag_name.strip().lstrip('#')
                if clean_tag:
                    supabase_client.table('tags').upsert({'name': clean_tag}, on_conflict='name').execute()
                    tag_row = supabase_client.table('tags').select('id').eq('name', clean_tag).execute().data
                    if tag_row:
                        supabase_client.table('reel_tags').insert({
                            'reel_id': reel_id,
                            'tag_id': tag_row[0]['id']
                        }).execute()

        return get_supabase_reel(reel_id)
    except Exception as e:
        print(f"[Supabase insert_reel Error] {e}")
        return None

def update_supabase_reel(reel_id, updates, collection_id=None, tags=None):
    if not is_supabase_enabled():
        return None
    try:
        if updates:
            supabase_client.table('reels').update(updates).eq('id', reel_id).execute()

        if collection_id is not None:
            supabase_client.table('reel_collections').delete().eq('reel_id', reel_id).execute()
            if collection_id:
                supabase_client.table('reel_collections').insert({
                    'reel_id': reel_id,
                    'collection_id': int(collection_id)
                }).execute()

        if tags is not None and isinstance(tags, list):
            supabase_client.table('reel_tags').delete().eq('reel_id', reel_id).execute()
            for tag_name in tags:
                clean_tag = tag_name.strip().lstrip('#')
                if clean_tag:
                    supabase_client.table('tags').upsert({'name': clean_tag}, on_conflict='name').execute()
                    tag_row = supabase_client.table('tags').select('id').eq('name', clean_tag).execute().data
                    if tag_row:
                        supabase_client.table('reel_tags').insert({
                            'reel_id': reel_id,
                            'tag_id': tag_row[0]['id']
                        }).execute()

        return get_supabase_reel(reel_id)
    except Exception as e:
        print(f"[Supabase update_reel Error] {e}")
        return None

def delete_supabase_reel(reel_id):
    if not is_supabase_enabled():
        return False
    try:
        supabase_client.table('reels').delete().eq('id', reel_id).execute()
        return True
    except Exception as e:
        print(f"[Supabase delete_reel Error] {e}")
        return False

def get_supabase_collections():
    if not is_supabase_enabled():
        return None
    try:
        cols = supabase_client.table('collections').select('*').order('name').execute().data
        for c in cols:
            # Count active reels
            rc = supabase_client.table('reel_collections').select('reel_id', count='exact').eq('collection_id', c['id']).execute()
            c['reel_count'] = rc.count or 0
        return cols
    except Exception as e:
        print(f"[Supabase get_collections Error] {e}")
        return None

def insert_supabase_collection(name, description, color, icon):
    if not is_supabase_enabled():
        return None
    try:
        res = supabase_client.table('collections').insert({
            'name': name,
            'description': description,
            'color': color,
            'icon': icon
        }).execute().data
        if res:
            res[0]['reel_count'] = 0
            return res[0]
        return None
    except Exception as e:
        print(f"[Supabase insert_collection Error] {e}")
        return None

def delete_supabase_collection(col_id):
    if not is_supabase_enabled():
        return False
    try:
        supabase_client.table('collections').delete().eq('id', col_id).execute()
        return True
    except Exception as e:
        print(f"[Supabase delete_collection Error] {e}")
        return False
