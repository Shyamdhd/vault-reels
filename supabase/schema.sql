-- ==============================================================================
-- VAULT — Supabase PostgreSQL Database Schema
-- Production Migration for Creative Reels Inspiration Library
-- ==============================================================================

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. User Profiles Table (Linked to Supabase Auth)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    email TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Collections Table
CREATE TABLE IF NOT EXISTS public.collections (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    color TEXT DEFAULT '#4F46E5',
    icon TEXT DEFAULT 'folder',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Reels Table
CREATE TYPE save_status_type AS ENUM ('saved_video', 'saved_link', 'processing', 'failed');
CREATE TYPE media_type_enum AS ENUM ('video', 'link', 'image');

CREATE TABLE IF NOT EXISTS public.reels (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    original_url TEXT NOT NULL,
    normalized_url TEXT,
    title TEXT NOT NULL,
    description TEXT,
    creator_username TEXT,
    creator_avatar TEXT,
    thumbnail_url TEXT,
    video_storage_path TEXT,
    video_url TEXT,
    media_type TEXT DEFAULT 'video',
    save_status TEXT DEFAULT 'saved_video',
    duration TEXT DEFAULT '0:30',
    aspect_ratio TEXT DEFAULT '9:16',
    is_favorite BOOLEAN DEFAULT FALSE,
    is_watch_later BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Reel Collections Junction (Many-to-Many)
CREATE TABLE IF NOT EXISTS public.reel_collections (
    reel_id BIGINT REFERENCES public.reels(id) ON DELETE CASCADE,
    collection_id BIGINT REFERENCES public.collections(id) ON DELETE CASCADE,
    PRIMARY KEY (reel_id, collection_id)
);

-- 6. Tags & Reel Tags Junction
CREATE TABLE IF NOT EXISTS public.tags (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS public.reel_tags (
    reel_id BIGINT REFERENCES public.reels(id) ON DELETE CASCADE,
    tag_id BIGINT REFERENCES public.tags(id) ON DELETE CASCADE,
    PRIMARY KEY (reel_id, tag_id)
);

-- 7. Indexes for Fast Search and Filtering
CREATE INDEX IF NOT EXISTS idx_reels_user_id ON public.reels(user_id);
CREATE INDEX IF NOT EXISTS idx_reels_normalized_url ON public.reels(normalized_url);
CREATE INDEX IF NOT EXISTS idx_reels_created_at ON public.reels(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_collections_user_id ON public.collections(user_id);

-- 8. Row Level Security (RLS) Policies
-- Ensure users can only access their own private library and collections

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reels ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reel_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reel_tags ENABLE ROW LEVEL SECURITY;

-- Profiles: Users can read and update their own profile
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- Collections: Private to user
CREATE POLICY "Users can view own collections" ON public.collections
    FOR SELECT USING (auth.uid() IS NOT NULL AND auth.uid() = user_id);

CREATE POLICY "Users can create collections" ON public.collections
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL AND auth.uid() = user_id);

CREATE POLICY "Users can update own collections" ON public.collections
    FOR UPDATE USING (auth.uid() IS NOT NULL AND auth.uid() = user_id);

CREATE POLICY "Users can delete own collections" ON public.collections
    FOR DELETE USING (auth.uid() IS NOT NULL AND auth.uid() = user_id);

-- Reels: Private to user
CREATE POLICY "Users can view own reels" ON public.reels
    FOR SELECT USING (auth.uid() IS NOT NULL AND auth.uid() = user_id);

CREATE POLICY "Users can insert own reels" ON public.reels
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL AND auth.uid() = user_id);

CREATE POLICY "Users can update own reels" ON public.reels
    FOR UPDATE USING (auth.uid() IS NOT NULL AND auth.uid() = user_id);

CREATE POLICY "Users can delete own reels" ON public.reels
    FOR DELETE USING (auth.uid() IS NOT NULL AND auth.uid() = user_id);

-- Junction tables: Enforce reel ownership
CREATE POLICY "Users can manage reel_collections" ON public.reel_collections
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.reels r
            WHERE r.id = reel_collections.reel_id AND r.user_id = auth.uid()
        )
    );

CREATE POLICY "Tags are viewable by all users" ON public.tags
    FOR SELECT USING (true);

CREATE POLICY "Users can insert tags" ON public.tags
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

CREATE POLICY "Users can manage reel_tags" ON public.reel_tags
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.reels r
            WHERE r.id = reel_tags.reel_id AND r.user_id = auth.uid()
        )
    );

-- Composite Unique Indexes (Per-User Deduplication)
CREATE UNIQUE INDEX IF NOT EXISTS idx_reels_user_normalized_url ON public.reels (user_id, normalized_url) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_collections_user_name ON public.collections (user_id, name) WHERE user_id IS NOT NULL;

-- 9. Storage Bucket Setup (vault-media)
-- Insert a storage bucket for uploaded videos and thumbnails
INSERT INTO storage.buckets (id, name, public)
VALUES ('vault-media', 'vault-media', true)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Public media access" ON storage.objects
    FOR SELECT USING (bucket_id = 'vault-media');

CREATE POLICY "Authenticated users can upload media" ON storage.objects
    FOR INSERT WITH CHECK (bucket_id = 'vault-media');

-- 10. Automatic Profile Creation on Sign-Up Trigger
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, display_name, email, avatar_url)
    VALUES (
        new.id,
        COALESCE(new.raw_user_meta_data->>'full_name', 'Creative Creator'),
        new.email,
        COALESCE(new.raw_user_meta_data->>'avatar_url', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 11. Initial Default Collections Seed
INSERT INTO public.collections (name, description, color, icon)
VALUES
    ('Transitions', 'Creative camera & match cut transitions', '#06B6D4', 'wand-2'),
    ('Typography', 'Kinetic, 3D and editorial title animations', '#F59E0B', 'type'),
    ('UI/UX', 'Mobile interactions, glassmorphism & dashboard flows', '#8B5CF6', 'layout'),
    ('Motion Graphics', 'Abstract 3D renders, cyber HUDs, and VFX loops', '#10B981', 'activity'),
    ('Brand Ads', 'High production luxury and commercial reels', '#EC4899', 'badge-percent'),
    ('Cafes', 'Atmospheric B-roll, aesthetic pours, and hospitality', '#D97706', 'coffee'),
    ('Client References', 'Client proposal benchmarks and pitch moodboards', '#3B82F6', 'briefcase')
ON CONFLICT DO NOTHING;
