// Vault — Full-Stack Creative Reels Inspiration Library
// Core Client-Side Application Controller

let state = {
  reels: [],
  collections: [],
  tags: [],
  selectedReel: null,
  activeFilter: 'all', // 'all', 'favorite', 'watch_later', 'archived'
  activeCollectionId: null,
  activeTag: null,
  mediaType: 'all', // 'all', 'video', 'link'
  sort: 'latest',
  searchQuery: '',
  playerMode: 'auto', // 'auto', 'video', 'embed'
  user: {
    name: 'Alex Rivera',
    handle: '@alex_creates',
    avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80'
  }
};

// Centralized Authenticated Fetch Helper
async function authFetch(url, options = {}) {
  const token = localStorage.getItem('vault_token');
  options.headers = options.headers || {};
  if (token && !options.headers['Authorization']) {
    options.headers['Authorization'] = `Bearer ${token}`;
  }
  options.credentials = 'include';
  
  const res = await fetch(url, options);
  if (res.status === 401 && !url.includes('/api/auth/me')) {
    console.warn('Session expired or unauthorized. Redirecting to login.');
    handleLogout();
  }
  return res;
}

// Launch Splash Screen Dismissal
function dismissLaunchSplash() {
  const splash = document.getElementById('vaultLaunchSplash');
  if (splash && !splash.classList.contains('opacity-0')) {
    splash.classList.add('opacity-0', 'pointer-events-none');
    setTimeout(() => {
      try { splash.remove(); } catch (e) {}
    }, 700);
  }
}

// Initialize App on DOM Load
document.addEventListener('DOMContentLoaded', async () => {
  // Safety timeout: ensure splash never blocks UI even on slow connections
  setTimeout(() => dismissLaunchSplash(), 2200);

  // Initialize and verify user session
  await initUserSession();

  // Check URL params for PWA Web Share Target
  handleWebShareTarget();

  await checkSystemStatus();
  await loadCollections();
  await loadReels();
  await loadTags();

  setupGlobalEventListeners();

  // Smoothly fade out launch screen after initialization
  setTimeout(() => {
    dismissLaunchSplash();
  }, 1000);
});

// User Session Management
async function initUserSession() {
  const userJson = localStorage.getItem('vault_user');
  if (userJson) {
    try {
      const user = JSON.parse(userJson);
      updateSidebarUserProfile(user);
    } catch (e) {
      console.warn('Session parsing error:', e);
    }
  }

  // Verify server session
  try {
    const res = await authFetch('/api/auth/me');
    if (res.ok) {
      const data = await res.json();
      if (data.authenticated && data.user) {
        localStorage.setItem('vault_user', JSON.stringify(data.user));
        updateSidebarUserProfile(data.user);
        return;
      }
    }
  } catch (e) {
    console.warn('Auth check skipped:', e);
  }

  // If no user is logged in, redirect to login page
  if (!userJson) {
    window.location.href = '/login';
  }
}

function updateSidebarUserProfile(user) {
  const avatarEl = document.getElementById('sidebarUserAvatar');
  const mobAvatarEl = document.getElementById('mobileBottomUserAvatar');
  const nameEl = document.getElementById('sidebarUserName');
  const roleEl = document.getElementById('sidebarUserRole');
  if (avatarEl && user.avatar_url) avatarEl.src = user.avatar_url;
  if (mobAvatarEl && user.avatar_url) mobAvatarEl.src = user.avatar_url;
  if (nameEl && user.display_name) nameEl.innerText = user.display_name;
  if (roleEl) roleEl.innerText = user.role || user.email || 'Pro Library';
}

async function handleLogout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
  } catch (e) {}

  // Clear all user-scoped storage & caches
  Object.keys(localStorage).forEach(k => {
    if (k.startsWith('vault_')) localStorage.removeItem(k);
  });
  sessionStorage.clear();

  // Reset in-memory state
  state.reels = [];
  state.collections = [];
  state.tags = [];
  state.selectedReel = null;

  window.location.href = '/login';
}

// =========================================================================
// SNAPCHAT-STYLE AVATAR STUDIO & PROFILE CUSTOMIZATION SYSTEM
// =========================================================================
let currentSnapStyle = 'avataaars';
let currentSnapSeed = 'Felix';
let currentSnapBgColor = 'fffc00';
const SNAP_SEEDS = ['Felix', 'Alex', 'Maya', 'Neo', 'Luna', 'Zen', 'Aria', 'Leo', 'Nova', 'Kai', 'Milo', 'Zoe', 'Pixel', 'Harper', 'Orion'];
const SNAP_STYLES = ['avataaars', 'adventurer', 'bottts', 'micah', 'lorelei'];
const SNAP_COLORS = ['fffc00', 'b6e3f4', 'c0aede', 'ffd5dc', 'ffdfbf', 'd1d4f9', '10b981', '1e293b'];

function generateSnapUrl(style = currentSnapStyle, seed = currentSnapSeed, color = currentSnapBgColor) {
  return `https://api.dicebear.com/9.x/${style}/svg?seed=${encodeURIComponent(seed)}&backgroundColor=${color}`;
}

function switchAvatarTab(tabName) {
  const tabs = {
    snap: { btn: document.getElementById('tabBtnSnap'), content: document.getElementById('tabContentSnap') },
    presets: { btn: document.getElementById('tabBtnPresets'), content: document.getElementById('tabContentPresets') },
    url: { btn: document.getElementById('tabBtnUrl'), content: document.getElementById('tabContentUrl') }
  };

  Object.keys(tabs).forEach(k => {
    const item = tabs[k];
    if (!item.btn || !item.content) return;
    if (k === tabName) {
      item.content.classList.remove('hidden');
      item.btn.className = 'flex-1 py-1.5 text-xs font-bold rounded-lg transition bg-[#7D53FF] text-white shadow-xs flex items-center justify-center gap-1.5';
    } else {
      item.content.classList.add('hidden');
      item.btn.className = 'flex-1 py-1.5 text-xs font-semibold text-gray-600 hover:text-gray-900 rounded-lg transition flex items-center justify-center gap-1.5';
    }
  });
}

function selectSnapStyle(style) {
  currentSnapStyle = style;
  document.querySelectorAll('.snap-style-btn').forEach(btn => {
    if (btn.getAttribute('data-style') === style) {
      btn.className = 'snap-style-btn py-1.5 px-1 rounded-lg text-center border text-[11px] font-semibold bg-white border-[#7D53FF] text-[#7D53FF] shadow-2xs';
    } else {
      btn.className = 'snap-style-btn py-1.5 px-1 rounded-lg text-center border text-[11px] font-semibold bg-white border-gray-200 text-gray-700 hover:border-gray-300';
    }
  });

  applySnapAvatarToPreview();
}

function selectSnapColor(hexColor) {
  currentSnapBgColor = hexColor;
  document.querySelectorAll('.snap-color-btn').forEach(btn => {
    if (btn.getAttribute('data-color') === hexColor) {
      btn.classList.add('border-[#7D53FF]', 'ring-2', 'ring-[#7D53FF]/40');
      btn.classList.remove('border-white');
    } else {
      btn.classList.remove('border-[#7D53FF]', 'ring-2', 'ring-[#7D53FF]/40');
      btn.classList.add('border-white');
    }
  });

  applySnapAvatarToPreview();
}

function setSnapSeed(seed) {
  currentSnapSeed = seed;
  const seedInput = document.getElementById('snapSeedInput');
  if (seedInput) seedInput.value = seed;
  applySnapAvatarToPreview();
}

function onSnapSeedInput(val) {
  currentSnapSeed = val.trim() || 'Alex';
  applySnapAvatarToPreview();
}

function randomizeSnapSeed() {
  const randomSeed = SNAP_SEEDS[Math.floor(Math.random() * SNAP_SEEDS.length)];
  setSnapSeed(randomSeed);
}

function randomizeSnapAvatar() {
  currentSnapStyle = SNAP_STYLES[Math.floor(Math.random() * SNAP_STYLES.length)];
  currentSnapSeed = SNAP_SEEDS[Math.floor(Math.random() * SNAP_SEEDS.length)];
  currentSnapBgColor = SNAP_COLORS[Math.floor(Math.random() * SNAP_COLORS.length)];

  selectSnapStyle(currentSnapStyle);
  selectSnapColor(currentSnapBgColor);
  const seedInput = document.getElementById('snapSeedInput');
  if (seedInput) seedInput.value = currentSnapSeed;

  switchAvatarTab('snap');
  applySnapAvatarToPreview();
  showToast('🎲 Generated new Snapchat avatar!');
}

function applySnapAvatarToPreview() {
  const url = generateSnapUrl(currentSnapStyle, currentSnapSeed, currentSnapBgColor);
  const avatarInput = document.getElementById('editAvatarUrlInput');
  const avatarPreview = document.getElementById('editAvatarPreview');
  const badge = document.getElementById('avatarTypeBadge');
  const status = document.getElementById('avatarUploadStatus');

  if (avatarInput) avatarInput.value = url;
  if (avatarPreview) avatarPreview.src = url;
  if (badge) {
    badge.innerText = 'Snap Avatar';
    badge.className = 'text-[10px] px-2 py-0.5 rounded-full font-semibold bg-amber-100 text-amber-800';
  }
  if (status) {
    status.innerText = `Snapchat style: ${currentSnapStyle} (${currentSnapSeed})`;
  }
}

function setAvatarPreset(url) {
  const avatarInput = document.getElementById('editAvatarUrlInput');
  const avatarPreview = document.getElementById('editAvatarPreview');
  const badge = document.getElementById('avatarTypeBadge');
  const status = document.getElementById('avatarUploadStatus');

  if (avatarInput) avatarInput.value = url;
  if (avatarPreview) avatarPreview.src = url;
  if (badge) {
    badge.innerText = 'Photo Preset';
    badge.className = 'text-[10px] px-2 py-0.5 rounded-full font-semibold bg-blue-100 text-blue-800';
  }
  if (status) {
    status.innerText = 'Using curated creator headshot.';
  }
}

function onDirectUrlInput(url) {
  const avatarInput = document.getElementById('editAvatarUrlInput');
  const avatarPreview = document.getElementById('editAvatarPreview');
  const badge = document.getElementById('avatarTypeBadge');

  if (avatarInput) avatarInput.value = url;
  if (avatarPreview && url && url.startsWith('http')) {
    avatarPreview.src = url;
  }
  if (badge) {
    badge.innerText = 'Direct URL';
    badge.className = 'text-[10px] px-2 py-0.5 rounded-full font-semibold bg-purple-100 text-purple-800';
  }
}

async function handleAvatarFileUpload(event) {
  const file = event.target.files?.[0];
  if (!file) return;

  const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/svg+xml'];
  if (!validTypes.includes(file.type) && !file.name.match(/\.(jpg|jpeg|png|webp|gif|svg)$/i)) {
    alert('Please upload a valid image file (JPG, PNG, WebP, GIF, or SVG).');
    return;
  }

  if (file.size > 10 * 1024 * 1024) {
    alert('Image file is too large. Maximum size is 10 MB.');
    return;
  }

  const avatarPreview = document.getElementById('editAvatarPreview');
  const avatarInput = document.getElementById('editAvatarUrlInput');
  const statusText = document.getElementById('avatarUploadStatus');
  const badge = document.getElementById('avatarTypeBadge');
  const saveBtn = document.getElementById('saveProfileBtn');

  // Instant local preview
  const reader = new FileReader();
  reader.onload = (e) => {
    if (avatarPreview && e.target?.result) {
      avatarPreview.src = e.target.result;
    }
  };
  reader.readAsDataURL(file);

  if (statusText) {
    statusText.innerHTML = '<span class="text-[#7D53FF] font-semibold animate-pulse">Uploading photo to Vault Storage...</span>';
  }
  if (badge) {
    badge.innerText = 'Uploading...';
    badge.className = 'text-[10px] px-2 py-0.5 rounded-full font-semibold bg-[#7D53FF]/15 text-[#7D53FF]';
  }
  if (saveBtn) saveBtn.disabled = true;

  try {
    const formData = new FormData();
    formData.append('file', file);

    const res = await authFetch('/api/upload', {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.error || 'Upload failed');
    }

    const uploadedUrl = data.url || data.video_url;
    if (avatarInput) avatarInput.value = uploadedUrl;
    if (avatarPreview) avatarPreview.src = uploadedUrl;
    if (badge) {
      badge.innerText = 'Uploaded Photo';
      badge.className = 'text-[10px] px-2 py-0.5 rounded-full font-semibold bg-emerald-100 text-emerald-800';
    }
    if (statusText) {
      statusText.innerText = 'Photo uploaded securely to Vault Storage!';
    }
    showToast('Photo uploaded successfully!');
  } catch (err) {
    console.error('Avatar upload error:', err);
    if (statusText) {
      statusText.innerHTML = `<span class="text-red-500 font-semibold">Upload failed: ${err.message}</span>`;
    }
    showToast('Failed to upload image. Please try again.');
  } finally {
    if (saveBtn) saveBtn.disabled = false;
    event.target.value = '';
  }
}

// Profile Settings Modal Handlers
function openProfileSettingsModal() {
  let user = {
    display_name: 'Alex Rivera',
    email: 'alex@vaultcreative.design',
    avatar_url: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80',
    role: 'Pro Creator'
  };

  const userJson = localStorage.getItem('vault_user');
  if (userJson) {
    try {
      user = { ...user, ...JSON.parse(userJson) };
    } catch (e) {}
  }

  const nameInput = document.getElementById('editDisplayNameInput');
  const roleInput = document.getElementById('editRoleInput');
  const emailInput = document.getElementById('editEmailInput');
  const avatarInput = document.getElementById('editAvatarUrlInput');
  const directUrlInput = document.getElementById('directAvatarUrlInput');
  const avatarPreview = document.getElementById('editAvatarPreview');
  const badge = document.getElementById('avatarTypeBadge');

  if (nameInput) nameInput.value = user.display_name || '';
  if (roleInput) roleInput.value = user.role || '';
  if (emailInput) emailInput.value = user.email || '';
  if (avatarInput) avatarInput.value = user.avatar_url || '';
  if (directUrlInput) directUrlInput.value = user.avatar_url || '';
  if (avatarPreview && user.avatar_url) avatarPreview.src = user.avatar_url;

  // Detect avatar type
  if (user.avatar_url && user.avatar_url.includes('api.dicebear.com')) {
    if (badge) {
      badge.innerText = 'Snap Avatar';
      badge.className = 'text-[10px] px-2 py-0.5 rounded-full font-semibold bg-amber-100 text-amber-800';
    }
    switchAvatarTab('snap');
  } else if (user.avatar_url && user.avatar_url.includes('images.unsplash.com')) {
    if (badge) {
      badge.innerText = 'Photo Preset';
      badge.className = 'text-[10px] px-2 py-0.5 rounded-full font-semibold bg-blue-100 text-blue-800';
    }
    switchAvatarTab('presets');
  } else if (user.avatar_url && user.avatar_url.includes('supabase.co')) {
    if (badge) {
      badge.innerText = 'Uploaded Photo';
      badge.className = 'text-[10px] px-2 py-0.5 rounded-full font-semibold bg-emerald-100 text-emerald-800';
    }
  }

  const modal = document.getElementById('profileSettingsModal');
  if (modal) modal.classList.remove('hidden');
  if (window.lucide) lucide.createIcons();
}

function closeProfileSettingsModal() {
  const modal = document.getElementById('profileSettingsModal');
  if (modal) modal.classList.add('hidden');
}

function updateAvatarPreview(url) {
  const avatarPreview = document.getElementById('editAvatarPreview');
  if (avatarPreview && url && url.startsWith('http')) {
    avatarPreview.src = url;
  }
}

async function handleSaveProfile(e) {
  e.preventDefault();
  const nameInput = document.getElementById('editDisplayNameInput');
  const roleInput = document.getElementById('editRoleInput');
  const emailInput = document.getElementById('editEmailInput');
  const avatarInput = document.getElementById('editAvatarUrlInput');
  const saveBtn = document.getElementById('saveProfileBtn');

  const displayName = nameInput?.value.trim();
  const role = roleInput?.value.trim() || 'Creator Member';
  const email = emailInput?.value.trim() || '';
  const avatarUrl = avatarInput?.value.trim() || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&h=120&q=80';

  if (!displayName) {
    alert('Please provide a display name');
    return;
  }

  let user = {};
  const userJson = localStorage.getItem('vault_user');
  if (userJson) {
    try { user = JSON.parse(userJson); } catch (e) {}
  }

  user.display_name = displayName;
  user.role = role;
  user.email = email;
  user.avatar_url = avatarUrl;

  // Persist locally
  localStorage.setItem('vault_user', JSON.stringify(user));
  updateSidebarUserProfile(user);

  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Saving...</span>';
    if (window.lucide) lucide.createIcons();
  }

  // Sync with backend API
  try {
    await authFetch('/api/auth/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(user)
    });
  } catch (err) {
    console.warn('Profile sync note:', err);
  } finally {
    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = '<i data-lucide="check" class="w-3.5 h-3.5"></i><span>Save Profile</span>';
      if (window.lucide) lucide.createIcons();
    }
  }

  closeProfileSettingsModal();
  showToast('Profile updated successfully!');
}

// Sync Supabase & Vercel deployment status
async function checkSystemStatus() {
  try {
    const res = await authFetch('/api/status');
    const data = await res.json();
    const dbText = document.getElementById('systemStatusDbText');
    const platformText = document.getElementById('systemStatusPlatformText');
    if (dbText) dbText.innerText = data.database;
    if (platformText) platformText.innerText = data.platform;
  } catch (err) {
    console.log('System status check skipped:', err);
  }
}

// =========================================================================
// PWA SERVICE WORKER & APP INSTALLATION SYSTEM
// =========================================================================
let deferredPwaPrompt = null;

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js')
      .then((reg) => console.log('[PWA] Service Worker active with scope:', reg.scope))
      .catch((err) => console.warn('[PWA] Service Worker registration note:', err));
  });
}

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPwaPrompt = e;
  console.log('[PWA] Native install prompt captured');
  
  const installBtn = document.getElementById('installAppSidebarBtn');
  if (installBtn) {
    installBtn.classList.add('ring-2', 'ring-[#B6FF00]', 'animate-pulse');
    setTimeout(() => installBtn.classList.remove('animate-pulse'), 3000);
  }
});

window.addEventListener('appinstalled', () => {
  deferredPwaPrompt = null;
  showToast('🎉 Vault App installed successfully!');
  const installBtn = document.getElementById('installAppSidebarBtn');
  if (installBtn) {
    installBtn.innerHTML = `
      <span class="flex items-center gap-2">
        <i data-lucide="check-circle-2" class="w-3.5 h-3.5 text-emerald-400"></i>
        <span>App Installed</span>
      </span>
      <span class="text-[9px] uppercase px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">READY</span>
    `;
    if (window.lucide) lucide.createIcons();
  }
});

function handlePwaInstallClick() {
  if (deferredPwaPrompt) {
    triggerNativeInstall();
  } else {
    openInstallAppModal();
  }
}

function triggerNativeInstall() {
  if (deferredPwaPrompt) {
    deferredPwaPrompt.prompt();
    deferredPwaPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        console.log('[PWA] User accepted installation prompt');
        showToast('Installing Vault App...');
      }
      deferredPwaPrompt = null;
      closeInstallAppModal();
    });
  } else {
    closeInstallAppModal();
    showToast('Follow the on-screen browser instructions to install.');
  }
}

function openInstallAppModal() {
  const modal = document.getElementById('installAppModal');
  if (modal) modal.classList.remove('hidden');
  if (window.lucide) lucide.createIcons();
}

function closeInstallAppModal() {
  const modal = document.getElementById('installAppModal');
  if (modal) modal.classList.add('hidden');
}

// PWA Web Share Target Handler
function handleWebShareTarget() {
  const urlParams = new URLSearchParams(window.location.search);
  const rawInput = urlParams.get('share_url') || urlParams.get('text') || urlParams.get('url');
  
  // Also check action shortcuts like ?action=add or ?action=profile
  const action = urlParams.get('action');
  if (action === 'add') {
    setTimeout(() => openAddReelModal(), 300);
  } else if (action === 'profile' || action === 'settings') {
    setTimeout(() => openProfileSettingsModal(), 300);
  }

  if (rawInput) {
    const urlMatch = rawInput.match(/https?:\/\/(?:www\.)?instagram\.com\/(?:reel|p|reels)\/[a-zA-Z0-9_\-]+[^\s]*/i);
    const targetUrl = urlMatch ? urlMatch[0] : (rawInput.includes('instagram.com') ? rawInput.trim() : null);
    if (targetUrl) {
      setTimeout(() => {
        openAddReelModal();
        const input = document.getElementById('reelUrlInput');
        if (input) {
          input.value = targetUrl;
          handleUrlValidation(targetUrl);
        }
      }, 400);
    }
  }
}

// Fetch Collections from Backend
async function loadCollections() {
  try {
    const res = await authFetch('/api/collections');
    const data = await res.json();
    state.collections = data.collections || [];
    renderCollectionsSidebar();
    populateCollectionSelects();
  } catch (err) {
    console.error('Failed to load collections:', err);
  }
}

// Fetch Tags from Backend
async function loadTags() {
  try {
    const res = await authFetch('/api/tags');
    const data = await res.json();
    state.tags = data.tags || [];
  } catch (err) {
    console.error('Failed to load tags:', err);
  }
}

// Fetch Reels from Backend with Filters & Search
async function loadReels() {
  const grid = document.getElementById('reelsGrid');
  if (grid) {
    grid.innerHTML = getSkeletonCardsHTML(6);
  }

  try {
    const params = new URLSearchParams();
    if (state.activeFilter && state.activeFilter !== 'all') {
      params.append('status', state.activeFilter);
    }
    if (state.activeCollectionId && state.activeCollectionId !== 'all') {
      params.append('collection', state.activeCollectionId);
    }
    if (state.activeTag) {
      params.append('tag', state.activeTag);
    }
    if (state.mediaType && state.mediaType !== 'all') {
      params.append('type', state.mediaType);
    }
    if (state.searchQuery) {
      params.append('search', state.searchQuery);
    }
    if (state.sort) {
      params.append('sort', state.sort);
    }

    const res = await authFetch(`/api/reels?${params.toString()}`);
    const data = await res.json();
    state.reels = data.reels || [];

    renderReelsGrid();
    updateReelCount(data.count || 0);

    // Auto-select first reel on desktop if none selected or selected reel is filtered out
    if (state.reels.length > 0) {
      const stillExists = state.selectedReel && state.reels.some(r => r.id === state.selectedReel.id);
      if (!stillExists) {
        if (window.innerWidth >= 1280) {
          selectReel(state.reels[0].id);
        } else {
          state.selectedReel = null;
        }
      } else {
        renderRightPreview(state.selectedReel);
      }
    } else {
      state.selectedReel = null;
      renderRightPreview(null);
    }
  } catch (err) {
    console.error('Failed to load reels:', err);
    if (grid) {
      grid.innerHTML = `
        <div class="col-span-3 py-16 text-center text-gray-500">
          <p class="text-sm">Unable to connect to server. Please try refreshing.</p>
        </div>
      `;
    }
  }
}

// Render Sidebar Collections List
function renderCollectionsSidebar() {
  const list = document.getElementById('collectionsSidebarList');
  if (!list) return;

  const totalReelsCount = state.collections.reduce((sum, c) => sum + (c.reel_count || 0), 0);

  let html = `
    <button onclick="filterByCollection(null)" class="sidebar-item w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition ${state.activeCollectionId === null ? 'bg-[#7D53FF]/20 text-[#B6FF00] font-bold' : 'text-gray-300 hover:text-white hover:bg-white/5'}">
      <span class="flex items-center gap-2.5">
        <span class="w-2 h-2 rounded-full bg-[#B6FF00]"></span>
        <span>All Reels</span>
      </span>
      <span class="text-[11px] text-gray-500 font-mono">${state.reels.length}</span>
    </button>
  `;

  state.collections.forEach(col => {
    const isActive = state.activeCollectionId === col.id;
    html += `
      <div class="group flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition cursor-pointer ${isActive ? 'bg-[#7D53FF]/20 text-white font-bold' : 'text-gray-300 hover:text-white hover:bg-white/5'}" onclick="filterByCollection(${col.id})">
        <span class="flex items-center gap-2.5 truncate">
          <span class="w-2 h-2 rounded-full shrink-0" style="background-color: ${col.color || '#7D53FF'}"></span>
          <span class="truncate">${escapeHtml(col.name)}</span>
        </span>
        <div class="flex items-center gap-1.5">
          <span class="text-[11px] text-gray-500 font-mono">${col.reel_count || 0}</span>
          <button onclick="event.stopPropagation(); deleteCollection(${col.id}, '${escapeHtml(col.name)}')" class="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 p-0.5 rounded transition" title="Delete Collection">
            <i data-lucide="trash-2" class="w-3 h-3"></i>
          </button>
        </div>
      </div>
    `;
  });

  list.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

// Populate dropdowns in modals
function populateCollectionSelects() {
  const selects = ['addReelCollectionSelect', 'previewCollectionSelect'];
  selects.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    let options = `<option value="">Uncategorized</option>`;
    state.collections.forEach(c => {
      options += `<option value="${c.id}">${escapeHtml(c.name)}</option>`;
    });
    el.innerHTML = options;
  });
}

// Render 3-Column Library Grid (4:5 Card Aspect)
function renderReelsGrid() {
  const grid = document.getElementById('reelsGrid');
  if (!grid) return;

  if (state.reels.length === 0) {
    grid.innerHTML = `
      <div class="col-span-1 md:col-span-2 xl:col-span-3 py-20 text-center flex flex-col items-center justify-center">
        <div class="w-16 h-16 rounded-2xl bg-[#7D53FF]/10 flex items-center justify-center text-[#7D53FF] mb-3 shadow-inner">
          <i data-lucide="film" class="w-8 h-8"></i>
        </div>
        <h3 class="font-semibold text-base text-gray-900">No reels found in this view</h3>
        <p class="text-xs text-gray-500 max-w-sm mt-1 mb-4">Paste an Instagram Reel link or upload your own 9:16 reference video to start building your creative vault.</p>
        <button onclick="openAddReelModal()" class="px-4 py-2 rounded-xl bg-[#7D53FF] hover:bg-[#6C40E8] text-white text-xs font-semibold shadow-md shadow-[#7D53FF]/20 transition flex items-center gap-2">
          <i data-lucide="plus" class="w-4 h-4"></i> Add Your First Reel
        </button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  let html = '';
  state.reels.forEach(reel => {
    const isSelected = state.selectedReel && state.selectedReel.id === reel.id;
    const primaryCol = reel.primary_collection;
    const colColor = primaryCol?.color || '#7D53FF';
    const colName = primaryCol?.name || 'Inspiration';

    const isPost = reel.media_type === 'post' || reel.save_status === 'saved_post' || isInstagramPostUrl(reel.original_url || reel.normalized_url);

    // Status Indicator
    let statusBadge = '';
    if (isPost) {
      statusBadge = `<span class="bg-[#7D53FF]/90 text-white text-[9px] font-bold px-2 py-0.5 rounded-full backdrop-blur-md flex items-center gap-1 shadow-sm"><i data-lucide="image" class="w-2.5 h-2.5"></i> Post</span>`;
    } else if (reel.save_status === 'saved_video') {
      statusBadge = `<span class="bg-emerald-500/90 text-white text-[9px] font-bold px-2 py-0.5 rounded-full backdrop-blur-md flex items-center gap-1 shadow-sm"><i data-lucide="film" class="w-2.5 h-2.5"></i> Reel</span>`;
    } else if (reel.save_status === 'saved_link') {
      statusBadge = `<span class="bg-blue-500/90 text-white text-[9px] font-bold px-2 py-0.5 rounded-full backdrop-blur-md flex items-center gap-1 shadow-sm"><i data-lucide="link" class="w-2.5 h-2.5"></i> Link</span>`;
    } else {
      statusBadge = `<span class="bg-amber-500/90 text-white text-[9px] font-bold px-2 py-0.5 rounded-full backdrop-blur-md flex items-center gap-1 shadow-sm">Syncing</span>`;
    }

    html += `
      <div onclick="selectReel(${reel.id})" class="reel-card ${isSelected ? 'active-reel' : ''} bg-white rounded-2xl border border-gray-200 overflow-hidden cursor-pointer group flex flex-col justify-between" id="reel-card-${reel.id}">
        
        <!-- Thumbnail Container (4:5 Aspect Ratio) -->
        <div class="relative aspect-thumbnail w-full bg-slate-900 overflow-hidden">
          <img src="${escapeHtml(reel.thumbnail_url)}" onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&h=750&q=80';" alt="${escapeHtml(reel.title)}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 ease-out" loading="lazy">
          
          <!-- Gradient Scrim -->
          <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/20"></div>

          <!-- Top Status & Duration Bar -->
          <div class="absolute top-2.5 left-2.5 right-2.5 flex items-center justify-between">
            ${statusBadge}
            ${!isPost && reel.duration ? `<span class="text-[10px] font-mono px-2 py-0.5 rounded-full bg-black/60 text-white/90 backdrop-blur-md border border-white/10">${reel.duration}</span>` : `<span class="text-[10px] font-medium px-2 py-0.5 rounded-full bg-black/60 text-white/90 backdrop-blur-md border border-white/10 flex items-center gap-1"><i data-lucide="image" class="w-2.5 h-2.5"></i> Photo</span>`}
          </div>

          <!-- Hover Action Overlay -->
          <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
            <div class="w-12 h-12 rounded-full bg-white/95 text-[#7D53FF] shadow-xl flex items-center justify-center transform group-hover:scale-110 transition-transform">
              <i data-lucide="${isPost ? 'eye' : 'play'}" class="w-5 h-5 ${isPost ? '' : 'fill-current ml-0.5'}"></i>
            </div>
          </div>

          <!-- Bottom Card Overlay Text -->
          <div class="absolute bottom-3 left-3 right-3 text-white">
            <div class="flex items-center gap-1.5 text-[11px] font-semibold text-gray-200 mb-1">
              <i data-lucide="instagram" class="w-3.5 h-3.5 text-pink-400"></i>
              <span class="truncate">${escapeHtml(reel.creator_username || '@instagram')}</span>
            </div>
            <h4 class="font-semibold text-xs text-white leading-snug line-clamp-2">${escapeHtml(reel.title)}</h4>
          </div>
        </div>

        <!-- Card Footer -->
        <div class="p-3 bg-white border-t border-gray-100 flex items-center justify-between">
          <span class="text-[11px] font-semibold px-2 py-0.5 rounded-md" style="background-color: ${colColor}15; color: ${colColor}; border: 1px solid ${colColor}30;">
            ${escapeHtml(colName)}
          </span>
          <div class="flex items-center gap-1 text-gray-400">
            <button onclick="event.stopPropagation(); toggleFavorite(${reel.id})" class="p-1.5 rounded-lg hover:bg-gray-100 transition ${reel.is_favorite ? 'text-amber-500' : 'hover:text-gray-600'}" title="Toggle Favorite">
              <i data-lucide="star" class="w-3.5 h-3.5 ${reel.is_favorite ? 'fill-current' : ''}"></i>
            </button>
            <button onclick="event.stopPropagation(); toggleWatchLater(${reel.id})" class="p-1.5 rounded-lg hover:bg-gray-100 transition ${reel.is_watch_later ? 'text-[#7D53FF]' : 'hover:text-gray-600'}" title="Watch Later">
              <i data-lucide="clock" class="w-3.5 h-3.5 ${reel.is_watch_later ? 'fill-current' : ''}"></i>
            </button>
          </div>
        </div>

      </div>
    `;
  });

  grid.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

// Select Reel and Update Right Preview Panel
function selectReel(id) {
  const reel = state.reels.find(r => r.id === id);
  if (!reel) return;

  state.selectedReel = reel;

  // Update card active classes
  document.querySelectorAll('.reel-card').forEach(c => c.classList.remove('active-reel'));
  const card = document.getElementById(`reel-card-${id}`);
  if (card) card.classList.add('active-reel');

  renderRightPreview(reel);

  // On mobile & tablet (< 1280px), open preview as full-screen modal
  if (window.innerWidth < 1280) {
    const aside = document.getElementById('rightPreviewAside');
    if (aside) {
      aside.classList.remove('hidden');
      aside.classList.add('fixed', 'inset-0', 'z-50', 'w-full', 'h-full', 'flex');
      aside.scrollTop = 0;
      if (window.lucide) lucide.createIcons();
    }
  }
}

function closeMobilePreview() {
  const aside = document.getElementById('rightPreviewAside');
  if (aside) {
    aside.classList.add('hidden');
    aside.classList.remove('fixed', 'inset-0', 'z-50', 'w-full', 'h-full', 'flex');
  }
  const video = document.getElementById('previewPlayerVideo');
  if (video) video.pause();
}

// Render Right Preview Panel Details
function extractInstagramShortcode(url) {
  if (!url) return null;
  const match = url.match(/instagram\.com\/(?:reel|p|reels|share\/p|share\/reel)\/([A-Za-z0-9_-]+)/);
  return match ? match[1] : null;
}

function isInstagramPostUrl(url) {
  if (!url) return false;
  return url.includes('/p/') || url.includes('/share/p/');
}

function switchPlayerMode(mode, reelId) {
  state.playerMode = mode;
  const reel = (state.reels && state.reels.find(r => r.id === reelId)) || state.selectedReel;
  if (reel) renderRightPreview(reel);
}

function handleVideoPlayerError(reelId, shortcode, isPost = false) {
  console.warn(`[Vault Player] Direct stream unavailable for item #${reelId}. Seamlessly switching to Instagram Embed Player.`);
  if (shortcode) {
    const frame = document.getElementById('playerFrameContainer');
    const base = isPost ? 'p' : 'reel';
    if (frame) {
      frame.innerHTML = `
        <iframe id="previewPlayerIframe" src="https://www.instagram.com/${base}/${escapeHtml(shortcode)}/embed/" 
                class="w-full h-full border-0 rounded-2xl bg-black" 
                frameborder="0" scrolling="no" allowtransparency="true" allowfullscreen="true"></iframe>
      `;
    }
    state.playerMode = 'embed';
    if (window.lucide) lucide.createIcons();
  }
}

function renderRightPreview(reel) {
  const container = document.getElementById('rightPreviewContainer');
  if (!container) return;

  if (!reel) {
    container.innerHTML = `
      <div class="h-full flex flex-col items-center justify-center p-8 text-center text-gray-400">
        <div class="w-16 h-16 rounded-2xl bg-gray-50 flex items-center justify-center text-gray-300 mb-3">
          <i data-lucide="mouse-pointer-click" class="w-8 h-8"></i>
        </div>
        <p class="font-semibold text-gray-700 text-sm">Select any reel or post to preview</p>
        <p class="text-xs text-gray-400 mt-1">Watch video, inspect photos, swipe carousels, view tags, and copy source links.</p>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  const primaryCol = reel.primary_collection;
  const colColor = primaryCol?.color || '#7D53FF';

  const isPost = reel.media_type === 'post' || reel.save_status === 'saved_post' || isInstagramPostUrl(reel.original_url || reel.normalized_url);
  const shortcode = extractInstagramShortcode(reel.original_url || reel.normalized_url);
  const baseType = isPost ? 'p' : 'reel';
  const embedUrl = shortcode ? `https://www.instagram.com/${baseType}/${shortcode}/embed/` : null;
  const hasDirectVideo = !isPost && !!(reel.video_url || (reel.save_status === 'saved_video'));
  const videoSrc = reel.video_url || `/api/reels/${reel.id}/video`;

  // Dual-mode resolution:
  let isEmbedMode = false;
  if (state.playerMode === 'embed') {
    isEmbedMode = true;
  } else if (state.playerMode === 'photo' && isPost) {
    isEmbedMode = false;
  } else if (state.playerMode === 'video' && !isPost) {
    isEmbedMode = false;
  } else {
    isEmbedMode = isPost ? true : (!hasDirectVideo && !!embedUrl);
  }

  let mediaPlayerHtml = '';
  if (isPost) {
    if (!isEmbedMode) {
      // High-resolution photo view
      mediaPlayerHtml = `
        <div id="playerFrameContainer" class="relative w-full aspect-reel-player rounded-2xl bg-black overflow-hidden shadow-md flex items-center justify-center group">
          <img src="${escapeHtml(reel.thumbnail_url)}" alt="${escapeHtml(reel.title)}" class="w-full h-full object-contain bg-slate-950">
          <a href="${escapeHtml(reel.thumbnail_url)}" target="_blank" class="absolute bottom-3 right-3 px-2.5 py-1.5 rounded-xl bg-black/70 hover:bg-black/90 text-white text-[11px] font-semibold flex items-center gap-1.5 backdrop-blur-md transition shadow-md" title="Open full resolution photo">
            <i data-lucide="maximize-2" class="w-3.5 h-3.5 text-[#B6FF00]"></i>
            <span>Full Photo</span>
          </a>
        </div>
      `;
    } else {
      // Interactive Instagram Post Embed (Swipe Carousel, Likes, Full Text)
      mediaPlayerHtml = `
        <div id="playerFrameContainer" class="relative w-full aspect-reel-player rounded-2xl bg-black overflow-hidden shadow-md">
          <iframe id="previewPlayerIframe" src="${escapeHtml(embedUrl || `https://www.instagram.com/p/${shortcode}/embed/`)}" 
                  class="w-full h-full border-0 rounded-2xl bg-black" 
                  frameborder="0" scrolling="no" allowtransparency="true" allowfullscreen="true"></iframe>
        </div>
      `;
    }
  } else {
    // Reel / Video Mode
    if (isEmbedMode && embedUrl) {
      mediaPlayerHtml = `
        <div id="playerFrameContainer" class="relative w-full aspect-reel-player rounded-2xl bg-black overflow-hidden shadow-md">
          <iframe id="previewPlayerIframe" src="${escapeHtml(embedUrl)}" 
                  class="w-full h-full border-0 rounded-2xl bg-black" 
                  frameborder="0" scrolling="no" allowtransparency="true" allowfullscreen="true"></iframe>
        </div>
      `;
    } else {
      mediaPlayerHtml = `
        <div id="playerFrameContainer" class="relative w-full aspect-reel-player rounded-2xl bg-black overflow-hidden shadow-md flex items-center justify-center group">
          <video id="previewPlayerVideo" src="${escapeHtml(videoSrc)}" poster="${escapeHtml(reel.thumbnail_url || '')}" 
                 controls playsinline loop autoplay 
                 onerror="handleVideoPlayerError(${reel.id}, '${shortcode || ''}', false)"
                 class="w-full h-full object-cover"></video>
        </div>
      `;
    }
  }

  // Player mode switcher
  let playerToggleHtml = '';
  if (shortcode) {
    if (isPost) {
      playerToggleHtml = `
        <div class="flex items-center justify-between px-2.5 py-1.5 bg-gray-100/90 rounded-xl mb-1 text-xs">
          <span class="text-[11px] font-semibold text-gray-500 flex items-center gap-1.5">
            <i data-lucide="image" class="w-3.5 h-3.5 text-[#7D53FF]"></i> Post View
          </span>
          <div class="flex items-center gap-1 bg-gray-200/80 p-0.5 rounded-lg">
            <button type="button" onclick="switchPlayerMode('embed', ${reel.id})" 
                    class="px-2.5 py-0.5 rounded-md text-[10px] font-bold transition ${isEmbedMode ? 'bg-[#7D53FF] text-white shadow-xs' : 'text-gray-600 hover:text-gray-900'}">
              Interactive Post
            </button>
            <button type="button" onclick="switchPlayerMode('photo', ${reel.id})" 
                    class="px-2.5 py-0.5 rounded-md text-[10px] font-bold transition ${!isEmbedMode ? 'bg-[#7D53FF] text-white shadow-xs' : 'text-gray-600 hover:text-gray-900'}">
              Photo Only
            </button>
          </div>
        </div>
      `;
    } else {
      playerToggleHtml = `
        <div class="flex items-center justify-between px-2.5 py-1.5 bg-gray-100/90 rounded-xl mb-1 text-xs">
          <span class="text-[11px] font-semibold text-gray-500 flex items-center gap-1.5">
            <i data-lucide="tv" class="w-3.5 h-3.5 text-[#7D53FF]"></i> Reel Player
          </span>
          <div class="flex items-center gap-1 bg-gray-200/80 p-0.5 rounded-lg">
            <button type="button" onclick="switchPlayerMode('video', ${reel.id})" 
                    class="px-2.5 py-0.5 rounded-md text-[10px] font-bold transition ${!isEmbedMode ? 'bg-[#7D53FF] text-white shadow-xs' : 'text-gray-600 hover:text-gray-900'}">
              Stream MP4
            </button>
            <button type="button" onclick="switchPlayerMode('embed', ${reel.id})" 
                    class="px-2.5 py-0.5 rounded-md text-[10px] font-bold transition ${isEmbedMode ? 'bg-[#7D53FF] text-white shadow-xs' : 'text-gray-600 hover:text-gray-900'}">
              Instagram Native
            </button>
          </div>
        </div>
      `;
    }
  }

  // Tags list HTML
  let tagsHtml = '';
  if (reel.tags && reel.tags.length > 0) {
    reel.tags.forEach(t => {
      tagsHtml += `<span class="text-[11px] font-medium bg-[#7D53FF]/10 text-[#7D53FF] border border-[#7D53FF]/20 px-2.5 py-1 rounded-lg">#${escapeHtml(t.name)}</span>`;
    });
  } else {
    tagsHtml = `<span class="text-xs text-gray-400 italic">No tags added yet</span>`;
  }

  container.innerHTML = `
    <div class="space-y-4 pb-12 xl:pb-0">
      
      <!-- Mobile Close / Back Bar (Visible on Mobile & Tablet < 1280px) -->
      <div class="xl:hidden flex items-center justify-between pb-3 border-b border-gray-100">
        <div class="flex items-center gap-2">
          <div class="w-7 h-7 rounded-lg ${isPost ? 'bg-indigo-100 text-[#7D53FF]' : 'bg-[#7D53FF]/15 text-[#7D53FF]'} flex items-center justify-center">
            <i data-lucide="${isPost ? 'image' : 'play'}" class="w-3.5 h-3.5 ${isPost ? '' : 'fill-current'}"></i>
          </div>
          <span class="font-bold text-xs text-[#242834]">${isPost ? 'Viewing Post' : 'Now Playing'}</span>
        </div>
        <button type="button" onclick="closeMobilePreview()" class="px-3 py-1.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-semibold flex items-center gap-1.5 transition">
          <i data-lucide="x" class="w-4 h-4"></i>
          <span>Close</span>
        </button>
      </div>
      
      <!-- Player Mode Switcher -->
      ${playerToggleHtml}

      <!-- Media Display Frame (9:16 Aspect Preserved) -->
      ${mediaPlayerHtml}

      <!-- Header & Title -->
      <div>
        <div class="flex items-center justify-between text-xs text-gray-500 mb-1.5">
          <span class="flex items-center gap-1.5 font-semibold text-gray-700">
            <img src="${escapeHtml(reel.creator_avatar || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=100&h=100&q=80')}" alt="Creator" class="w-5 h-5 rounded-full object-cover">
            <span>${escapeHtml(reel.creator_username || '@instagram_creator')}</span>
          </span>
          <span class="text-[11px] text-gray-400">Added ${formatDate(reel.created_at)}</span>
        </div>
        <h3 class="font-bold text-base text-gray-900 leading-snug">${escapeHtml(reel.title)}</h3>
      </div>

      <!-- Quick Action Buttons -->
      <div class="flex items-center gap-2 py-2 border-y border-gray-100">
        <a href="${escapeHtml(reel.original_url)}" target="_blank" class="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl border border-gray-200 text-xs font-semibold text-gray-700 hover:bg-gray-50 transition" title="Open source link">
          <i data-lucide="external-link" class="w-3.5 h-3.5 text-pink-500"></i> Source
        </a>
        <button onclick="toggleFavorite(${reel.id})" class="p-2 rounded-xl border border-gray-200 hover:bg-gray-50 transition ${reel.is_favorite ? 'text-amber-500 bg-amber-50 border-amber-200' : 'text-gray-500'}" title="Favorite">
          <i data-lucide="star" class="w-4 h-4 ${reel.is_favorite ? 'fill-current' : ''}"></i>
        </button>
        <button onclick="toggleWatchLater(${reel.id})" class="p-2 rounded-xl border border-gray-200 hover:bg-gray-50 transition ${reel.is_watch_later ? 'text-[#7D53FF] bg-[#7D53FF]/10 border-[#7D53FF]/30' : 'text-gray-500'}" title="Watch Later">
          <i data-lucide="clock" class="w-4 h-4 ${reel.is_watch_later ? 'fill-current' : ''}"></i>
        </button>
        <button onclick="toggleArchive(${reel.id})" class="p-2 rounded-xl border border-gray-200 hover:bg-gray-50 transition ${reel.is_archived ? 'text-[#7D53FF] bg-[#7D53FF]/10 border-[#7D53FF]/30' : 'text-gray-500'}" title="Archive">
          <i data-lucide="archive" class="w-4 h-4"></i>
        </button>
        <button onclick="deleteReel(${reel.id})" class="p-2 rounded-xl border border-gray-200 hover:bg-red-50 text-gray-500 hover:text-red-600 transition" title="Delete">
          <i data-lucide="trash-2" class="w-4 h-4"></i>
        </button>
      </div>

      <!-- Description / Caption -->
      <div class="space-y-1">
        <p class="text-xs font-semibold uppercase tracking-wider text-gray-400">Caption & Notes</p>
        <p class="text-xs text-gray-600 leading-relaxed max-h-24 overflow-y-auto pr-1">${escapeHtml(reel.description || 'No caption saved.')}</p>
      </div>

      <!-- Collection Assignment -->
      <div class="space-y-1.5">
        <p class="text-xs font-semibold uppercase tracking-wider text-gray-400">Collection</p>
        <div class="flex items-center gap-2">
          <select id="previewCollectionSelect" onchange="assignCollection(${reel.id}, this.value)" class="flex-1 text-xs bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 text-gray-800 focus:outline-none focus:border-[#7D53FF]">
            <option value="">Uncategorized</option>
            ${state.collections.map(c => `<option value="${c.id}" ${primaryCol?.id === c.id ? 'selected' : ''}>${escapeHtml(c.name)}</option>`).join('')}
          </select>
          <button onclick="openNewCollectionModal()" class="p-2 rounded-xl border border-gray-200 hover:bg-gray-100 text-gray-600" title="New Collection">
            <i data-lucide="folder-plus" class="w-4 h-4"></i>
          </button>
        </div>
      </div>

      <!-- Custom Tags -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <p class="text-xs font-semibold uppercase tracking-wider text-gray-400">Tags</p>
          <button onclick="promptAddTag(${reel.id})" class="text-[11px] font-semibold text-[#7D53FF] hover:text-[#6C40E8] flex items-center gap-1">
            <i data-lucide="plus" class="w-3 h-3"></i> Add Tag
          </button>
        </div>
        <div class="flex flex-wrap gap-1.5">
          ${tagsHtml}
        </div>
      </div>

      <!-- Primary CTA: Add to Collection / Move -->
      <div class="pt-2">
        <button onclick="document.getElementById('previewCollectionSelect').focus()" class="w-full py-2.5 rounded-xl bg-[#7D53FF] hover:bg-[#6C40E8] text-white text-xs font-bold shadow-md shadow-[#7D53FF]/20 transition flex items-center justify-center gap-2">
          <i data-lucide="folder-input" class="w-4 h-4"></i>
          <span>ADD TO COLLECTION</span>
        </button>
      </div>

    </div>
  `;

  if (window.lucide) lucide.createIcons();
}

// Add New Tag Prompt
async function promptAddTag(reelId) {
  const tagName = prompt('Enter a new tag for this reel:');
  if (!tagName || !tagName.trim()) return;

  const reel = state.reels.find(r => r.id === reelId);
  if (!reel) return;

  const currentTags = (reel.tags || []).map(t => t.name);
  if (currentTags.includes(tagName.trim())) {
    showToast('Tag already added');
    return;
  }

  currentTags.push(tagName.trim());
  await updateReelBackend(reelId, { tags: currentTags });
}

// Assign Collection in Backend
async function assignCollection(reelId, collectionId) {
  await updateReelBackend(reelId, { collection_id: collectionId ? parseInt(collectionId, 10) : null });
  await loadCollections();
}

// Toggle Favorite
async function toggleFavorite(reelId) {
  const reel = state.reels.find(r => r.id === reelId);
  if (!reel) return;
  const newFav = reel.is_favorite ? 0 : 1;
  reel.is_favorite = newFav;
  await updateReelBackend(reelId, { is_favorite: newFav });
  showToast(newFav ? 'Added to Favorites' : 'Removed from Favorites');
}

// Toggle Watch Later
async function toggleWatchLater(reelId) {
  const reel = state.reels.find(r => r.id === reelId);
  if (!reel) return;
  const newWl = reel.is_watch_later ? 0 : 1;
  reel.is_watch_later = newWl;
  await updateReelBackend(reelId, { is_watch_later: newWl });
  showToast(newWl ? 'Added to Watch Later' : 'Removed from Watch Later');
}

// Toggle Archive
async function toggleArchive(reelId) {
  const reel = state.reels.find(r => r.id === reelId);
  if (!reel) return;
  const newArchived = reel.is_archived ? 0 : 1;
  await updateReelBackend(reelId, { is_archived: newArchived });
  showToast(newArchived ? 'Reel Archived' : 'Reel Unarchived');
  await loadReels();
  await loadCollections();
}

// Delete Reel
async function deleteReel(reelId) {
  if (!confirm('Are you sure you want to remove this reel from Vault?')) return;
  try {
    const res = await authFetch(`/api/reels/${reelId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Reel deleted from Vault');
      await loadReels();
      await loadCollections();
    }
  } catch (err) {
    console.error('Delete error:', err);
  }
}

// Update Reel Backend Helper
async function updateReelBackend(reelId, payload) {
  try {
    const res = await authFetch(`/api/reels/${reelId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.reel) {
      const idx = state.reels.findIndex(r => r.id === reelId);
      if (idx !== -1) state.reels[idx] = data.reel;
      if (state.selectedReel && state.selectedReel.id === reelId) {
        state.selectedReel = data.reel;
        renderRightPreview(data.reel);
      }
      renderReelsGrid();
    }
  } catch (err) {
    console.error('Update error:', err);
  }
}

// Filter Navigation Actions
function filterByStatus(status) {
  state.activeFilter = status;
  state.activeCollectionId = null;
  state.activeTag = null;
  updateNavActiveState(status);
  loadReels();
  if (window.innerWidth < 1024) closeMobileSidebar();
}

function filterByCollection(colId) {
  state.activeCollectionId = colId;
  state.activeFilter = 'all';
  state.activeTag = null;
  renderCollectionsSidebar();
  updateNavActiveState('collections');
  loadReels();
  if (window.innerWidth < 1024) closeMobileSidebar();
}

function filterByMediaType(type) {
  state.mediaType = type;
  document.querySelectorAll('.media-type-btn').forEach(btn => {
    if (btn.dataset.type === type) {
      btn.classList.add('bg-white', 'text-gray-900', 'shadow-sm', 'font-semibold');
      btn.classList.remove('text-gray-500');
    } else {
      btn.classList.remove('bg-white', 'text-gray-900', 'shadow-sm', 'font-semibold');
      btn.classList.add('text-gray-500');
    }
  });
  loadReels();
}

function handleSortChange(sort) {
  state.sort = sort;
  loadReels();
}

function updateNavActiveState(name) {
  document.querySelectorAll('.nav-main-btn').forEach(btn => {
    if (btn.dataset.nav === name) {
      btn.classList.add('bg-[#7D53FF]/20', 'text-[#B6FF00]', 'font-bold');
      btn.classList.remove('text-gray-400');
    } else {
      btn.classList.remove('bg-[#7D53FF]/20', 'text-[#B6FF00]', 'font-bold');
      btn.classList.add('text-gray-400');
    }
  });
}

function updateReelCount(count) {
  const el = document.getElementById('headerReelsCount');
  if (el) el.innerText = `${count} saved references`;
}

// Add Reel Flow: URL validation and auto-fill
let verifiedUrlData = null;
async function handleUrlValidation(url) {
  const feedback = document.getElementById('urlValidationFeedback');
  if (!feedback) return;

  if (!url || !url.includes('instagram.com')) {
    feedback.innerHTML = `<span class="text-xs text-gray-400">Paste any public Instagram Reel URL (e.g., https://www.instagram.com/reel/...)</span>`;
    return;
  }

  feedback.innerHTML = `
    <span class="text-xs text-[#7D53FF] flex items-center gap-1.5 font-medium">
      <div class="w-3.5 h-3.5 border-2 border-[#7D53FF] border-t-transparent rounded-full animate-spin"></div>
      Validating link and extracting metadata...
    </span>
  `;

  try {
    const res = await authFetch('/api/parse-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await res.json();

    if (data.duplicate) {
      feedback.innerHTML = `
        <div class="p-2.5 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-center justify-between">
          <span class="flex items-center gap-1.5 font-semibold"><i data-lucide="alert-circle" class="w-4 h-4 text-amber-600"></i> ${data.message}</span>
          <button type="button" onclick="selectReel(${data.existing_reel.id}); closeAddReelModal();" class="underline font-bold text-amber-900">Jump to Reel</button>
        </div>
      `;
      if (window.lucide) lucide.createIcons();
      return;
    }

    verifiedUrlData = data;
    const isPost = data.is_post || data.media_type === 'post' || isInstagramPostUrl(url);
    const kindLabel = isPost ? 'Post' : 'Reel';

    feedback.innerHTML = `
      <div class="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-center gap-1.5 font-medium">
        <i data-lucide="check-circle" class="w-4 h-4 text-emerald-600"></i> Valid Instagram ${kindLabel} reference verified!
      </div>
    `;

    // Render Live Preview Card inside the modal
    const previewCard = document.getElementById('modalReelPreviewCard');
    if (previewCard) {
      previewCard.classList.remove('hidden');
      previewCard.innerHTML = `
        <div class="p-3 bg-slate-50 border border-[#7D53FF]/25 rounded-2xl flex items-center gap-3 shadow-xs">
          <div class="w-14 h-18 rounded-xl overflow-hidden bg-black shrink-0 relative shadow-sm border border-black/10">
            <img src="${escapeHtml(data.thumbnail_url)}" alt="Preview" class="w-full h-full object-cover">
            <div class="absolute inset-0 bg-black/25 flex items-center justify-center">
              <i data-lucide="${isPost ? 'image' : 'play'}" class="w-4 h-4 text-[#B6FF00] ${isPost ? '' : 'fill-[#B6FF00]'}"></i>
            </div>
          </div>
          <div class="flex-1 min-w-0 space-y-0.5">
            <div class="flex items-center gap-1.5">
              <span class="text-[11px] font-bold text-[#7D53FF] truncate">${escapeHtml(data.creator_username || '@creator')}</span>
              <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-gray-200/70 text-gray-700 font-semibold">${isPost ? 'Photo / Carousel' : escapeHtml(data.duration || '0:30')}</span>
            </div>
            <p class="text-xs font-bold text-gray-900 truncate leading-snug">${escapeHtml(data.title)}</p>
            <p class="text-[11px] text-gray-500 truncate">${escapeHtml(data.description || `Instagram ${kindLabel} reference`)}</p>
          </div>
          <div class="shrink-0 text-right">
            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold ${isPost ? 'bg-[#7D53FF]/15 text-[#7D53FF] border border-[#7D53FF]/25' : (data.video_url ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' : 'bg-purple-100 text-[#7D53FF] border border-[#7D53FF]/20')}">
              <i data-lucide="${isPost ? 'image' : (data.video_url ? 'video' : 'play-circle')}" class="w-3 h-3"></i>
              ${isPost ? 'Post Ready' : (data.video_url ? 'Video Ready' : 'Embed Ready')}
            </span>
          </div>
        </div>
      `;
    }

    // Auto-fill form
    const titleInput = document.getElementById('reelTitleInput');
    const creatorInput = document.getElementById('reelCreatorInput');
    const descInput = document.getElementById('reelDescInput');
    const videoInput = document.getElementById('uploadedVideoUrlInput');
    if (titleInput) titleInput.value = data.title;
    if (creatorInput) creatorInput.value = data.creator_username;
    if (descInput && !descInput.value) descInput.value = data.description;
    if (videoInput && data.video_url) videoInput.value = data.video_url;

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    feedback.innerHTML = `<span class="text-xs text-red-500">Could not validate link. You can still save it manually.</span>`;
  }
}

// Submit Add Reel / Post Form
async function submitAddReel() {
  const url = document.getElementById('reelUrlInput')?.value.trim();
  let title = document.getElementById('reelTitleInput')?.value.trim();
  let creator = document.getElementById('reelCreatorInput')?.value.trim();
  let desc = document.getElementById('reelDescInput')?.value.trim();
  const collectionId = document.getElementById('addReelCollectionSelect')?.value;
  const rawTags = document.getElementById('reelTagsInput')?.value.trim();
  const videoUrl = document.getElementById('uploadedVideoUrlInput')?.value.trim() || verifiedUrlData?.video_url;

  const isPost = verifiedUrlData?.is_post || verifiedUrlData?.media_type === 'post' || isInstagramPostUrl(url);
  const kindLabel = isPost ? 'Post' : 'Reel';
  const mediaType = isPost ? 'post' : (videoUrl ? 'video' : 'reel');
  const saveStatus = isPost ? 'saved_post' : (videoUrl ? 'saved_video' : 'saved_link');

  if (!title) {
    title = verifiedUrlData?.title || (url ? `Instagram ${kindLabel} (${extractInstagramShortcode(url) || 'Reference'})` : '');
  }
  if (!creator) {
    creator = verifiedUrlData?.creator_username || '@instagram_creator';
  }
  if (!desc) {
    desc = verifiedUrlData?.description || `Saved Instagram ${kindLabel} inspiration.`;
  }

  if (!title && !url) {
    alert('Please provide an Instagram link or title.');
    return;
  }

  const tags = rawTags ? rawTags.split(',').map(t => t.trim()) : [];

  const payload = {
    original_url: url,
    title: title || `Instagram ${kindLabel} Reference`,
    creator_username: creator,
    description: desc,
    collection_id: collectionId ? parseInt(collectionId, 10) : null,
    tags,
    video_url: videoUrl || null,
    thumbnail_url: verifiedUrlData?.thumbnail_url || 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=600&h=750&q=80',
    media_type: mediaType,
    save_status: saveStatus
  };

  try {
    const res = await authFetch('/api/reels', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    let data;
    try {
      data = await res.json();
    } catch (parseErr) {
      data = { error: `Server responded with status ${res.status}` };
    }
    if (res.ok) {
      showToast(`${kindLabel} saved to Vault!`);
      closeAddReelModal();
      await loadReels();
      await loadCollections();
      if (data.reel) selectReel(data.reel.id);
    } else {
      alert(data.error || 'Failed to save item');
    }
  } catch (err) {
    console.error('Save error:', err);
    alert('An error occurred while saving: ' + (err.message || 'Please check your connection and try again.'));
  }
}

// Direct Video Upload Handler
async function handleVideoFileUpload(file) {
  if (!file) return;
  const statusEl = document.getElementById('uploadProgressStatus');
  const progressBar = document.getElementById('uploadProgressBar');
  const progressContainer = document.getElementById('uploadProgressContainer');

  if (progressContainer) progressContainer.classList.remove('hidden');
  if (statusEl) statusEl.innerText = `Uploading ${file.name} (${(file.size / (1024*1024)).toFixed(1)} MB)...`;

  const formData = new FormData();
  formData.append('video', file);

  try {
    const res = await authFetch('/api/upload', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (res.ok && data.video_url) {
      document.getElementById('uploadedVideoUrlInput').value = data.video_url;
      if (statusEl) statusEl.innerText = 'Upload complete! Video saved securely in Vault storage.';
      if (progressBar) progressBar.style.width = '100%';
      showToast('Video uploaded successfully');
    } else {
      if (statusEl) statusEl.innerText = data.error || 'Upload failed.';
    }
  } catch (err) {
    if (statusEl) statusEl.innerText = 'Upload error. Please try again.';
  }
}

// Create New Collection
async function submitNewCollection() {
  const name = document.getElementById('newColNameInput')?.value.trim();
  const desc = document.getElementById('newColDescInput')?.value.trim();
  const color = document.getElementById('newColColorInput')?.value || '#7D53FF';

  if (!name) {
    alert('Please provide a collection name');
    return;
  }

  try {
    const res = await authFetch('/api/collections', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description: desc, color })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(`Collection "${name}" created!`);
      closeNewCollectionModal();
      await loadCollections();
    } else {
      alert(data.error || 'Failed to create collection');
    }
  } catch (err) {
    console.error('Collection create error:', err);
  }
}

// Delete Collection
async function deleteCollection(id, name) {
  if (!confirm(`Delete collection "${name}"? Reels inside will not be deleted.`)) return;
  try {
    const res = await authFetch(`/api/collections/${id}`, { method: 'DELETE' });
    if (res.ok) {
      showToast(`Collection "${name}" removed`);
      if (state.activeCollectionId === id) state.activeCollectionId = null;
      await loadCollections();
      await loadReels();
    }
  } catch (err) {
    console.error('Delete collection error:', err);
  }
}

// Mobile Navigation & Drawer Helpers
function openMobileSidebar() {
  const sidebar = document.getElementById('appSidebar');
  const backdrop = document.getElementById('mobileSidebarBackdrop');
  if (sidebar) sidebar.classList.remove('-translate-x-full');
  if (backdrop) backdrop.classList.remove('hidden');
}

function closeMobileSidebar() {
  const sidebar = document.getElementById('appSidebar');
  const backdrop = document.getElementById('mobileSidebarBackdrop');
  if (sidebar) sidebar.classList.add('-translate-x-full');
  if (backdrop) backdrop.classList.add('hidden');
}

function toggleMobileSidebar() {
  const sidebar = document.getElementById('appSidebar');
  if (sidebar && sidebar.classList.contains('-translate-x-full')) {
    openMobileSidebar();
  } else {
    closeMobileSidebar();
  }
}

function updateMobileBottomNav(tab) {
  const home = document.getElementById('mobNavHome');
  const fav = document.getElementById('mobNavFav');
  if (!home || !fav) return;
  if (tab === 'fav') {
    fav.className = 'flex flex-col items-center gap-0.5 py-1 text-[#B6FF00] font-bold transition';
    home.className = 'flex flex-col items-center gap-0.5 py-1 text-gray-400 hover:text-white transition';
  } else {
    home.className = 'flex flex-col items-center gap-0.5 py-1 text-[#B6FF00] font-bold transition';
    fav.className = 'flex flex-col items-center gap-0.5 py-1 text-gray-400 hover:text-white transition';
  }
}

// Modals UI Helpers
function openAddReelModal() {
  document.getElementById('addReelModal')?.classList.remove('hidden');
}

function closeAddReelModal() {
  document.getElementById('addReelModal')?.classList.add('hidden');
  const previewCard = document.getElementById('modalReelPreviewCard');
  if (previewCard) {
    previewCard.classList.add('hidden');
    previewCard.innerHTML = '';
  }
  const feedback = document.getElementById('urlValidationFeedback');
  if (feedback) {
    feedback.innerHTML = '<span class="text-[11px] text-gray-400">Links are verified for duplicate entries and public metadata.</span>';
  }
  const urlInput = document.getElementById('reelUrlInput');
  if (urlInput) urlInput.value = '';
  verifiedUrlData = null;
}

function openNewCollectionModal() {
  document.getElementById('newCollectionModal')?.classList.remove('hidden');
}

function closeNewCollectionModal() {
  document.getElementById('newCollectionModal')?.classList.add('hidden');
}

function openPwaShortcutModal() {
  document.getElementById('pwaShortcutModal')?.classList.remove('hidden');
}

function closePwaShortcutModal() {
  document.getElementById('pwaShortcutModal')?.classList.add('hidden');
}

// Toast System
function showToast(msg) {
  const toast = document.getElementById('appToast');
  const txt = document.getElementById('appToastText');
  if (!toast || !txt) return;

  txt.innerText = msg;
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 3000);
}

// Notifications System
function toggleNotificationsMenu(e) {
  if (e) e.stopPropagation();
  const dropdown = document.getElementById('notificationsDropdown');
  if (!dropdown) return;
  const isHidden = dropdown.classList.contains('hidden');
  if (isHidden) {
    dropdown.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
  } else {
    dropdown.classList.add('hidden');
  }
}

function markAllNotificationsAsRead() {
  const dot = document.getElementById('unreadNotifDot');
  const badge = document.getElementById('notifCountBadge');
  if (dot) dot.classList.add('hidden');
  if (badge) {
    badge.innerText = '0 new';
    badge.className = 'text-[10px] font-semibold bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full';
  }
  document.querySelectorAll('#notificationsList > div').forEach(item => {
    item.classList.remove('bg-[#7D53FF]/5', 'border-[#7D53FF]/20');
    item.classList.add('bg-white', 'border-gray-100');
  });
  showToast('All notifications marked as read');
}

function clearNotifications() {
  const list = document.getElementById('notificationsList');
  const dot = document.getElementById('unreadNotifDot');
  const badge = document.getElementById('notifCountBadge');
  if (dot) dot.classList.add('hidden');
  if (badge) {
    badge.innerText = '0';
    badge.className = 'text-[10px] font-semibold bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full';
  }
  if (list) {
    list.innerHTML = `
      <div class="py-8 text-center text-gray-400 space-y-1">
        <i data-lucide="bell-off" class="w-6 h-6 mx-auto text-gray-300"></i>
        <p class="text-xs font-medium">No new notifications</p>
        <p class="text-[10px] text-gray-400">You are completely up to date!</p>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
  }
}

// Global Event Listeners & Shortcuts
function setupGlobalEventListeners() {
  // Global Search Input with debounce
  let searchTimeout = null;
  const searchInput = document.getElementById('globalSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      state.searchQuery = e.target.value.trim();
      searchTimeout = setTimeout(() => loadReels(), 250);
    });
  }

  // URL input real-time validation
  let urlTimeout = null;
  const urlInput = document.getElementById('reelUrlInput');
  if (urlInput) {
    urlInput.addEventListener('input', (e) => {
      clearTimeout(urlTimeout);
      const url = e.target.value.trim();
      urlTimeout = setTimeout(() => handleUrlValidation(url), 400);
    });
  }

  // File drag & drop
  const dropZone = document.getElementById('videoDropZone');
  const fileInput = document.getElementById('videoFileInput');
  if (dropZone && fileInput) {
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
      if (e.target.files?.[0]) handleVideoFileUpload(e.target.files[0]);
    });
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('border-[#7D53FF]', 'bg-[#7D53FF]/5');
    });
    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('border-[#7D53FF]', 'bg-[#7D53FF]/5');
    });
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('border-[#7D53FF]', 'bg-[#7D53FF]/5');
      if (e.dataTransfer.files?.[0]) {
        handleVideoFileUpload(e.dataTransfer.files[0]);
      }
    });
  }

  // Close notifications dropdown on outside click
  document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('notificationsDropdown');
    const bellBtn = document.getElementById('notificationsBellBtn');
    if (dropdown && !dropdown.classList.contains('hidden')) {
      if (!dropdown.contains(e.target) && !bellBtn?.contains(e.target)) {
        dropdown.classList.add('hidden');
      }
    }
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Cmd/Ctrl + K or / to focus search
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      searchInput?.focus();
    }
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
      e.preventDefault();
      searchInput?.focus();
    }
    // Escape closes modals
    if (e.key === 'Escape') {
      closeAddReelModal();
      closeNewCollectionModal();
      closePwaShortcutModal();
      closeProfileSettingsModal();
      closeMobilePreview();
      closeMobileSidebar();
      const dropdown = document.getElementById('notificationsDropdown');
      if (dropdown) dropdown.classList.add('hidden');
    }
    // Space toggles video playback
    if (e.key === ' ' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
      const vid = document.getElementById('previewPlayerVideo');
      if (vid) {
        e.preventDefault();
        vid.paused ? vid.play() : vid.pause();
      }
    }
  });

  // Responsive window resize cleanup
  window.addEventListener('resize', () => {
    if (window.innerWidth >= 1280) {
      const aside = document.getElementById('rightPreviewAside');
      if (aside && aside.classList.contains('fixed')) {
        aside.classList.remove('fixed', 'inset-0', 'z-50', 'w-full', 'h-full');
      }
    }
    if (window.innerWidth >= 1024) {
      closeMobileSidebar();
    }
  });
}

// Helpers
function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  })[m]);
}

function formatDate(isoStr) {
  if (!isoStr) return 'Recently';
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return 'Recently';
  }
}

function getSkeletonCardsHTML(count) {
  let html = '';
  for (let i = 0; i < count; i++) {
    html += `
      <div class="bg-white rounded-2xl border border-gray-100 overflow-hidden flex flex-col">
        <div class="aspect-thumbnail w-full skeleton"></div>
        <div class="p-3 space-y-2">
          <div class="h-3 w-3/4 skeleton rounded"></div>
          <div class="h-2 w-1/2 skeleton rounded"></div>
        </div>
      </div>
    `;
  }
  return html;
}
