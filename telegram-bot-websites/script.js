const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

// Application state
const state = {
  items: [],
  filtered: [],
  filter: "all",
  sort: "newest",
  search: "",
  density: "dense",
  syncAt: null,
  initData: tg ? tg.initData : "",
  context: null,
  syncError: null,
  sessionMode: null,
  stats: { total: 0, videos: 0, images: 0, bytes: 0 },
  visibleCount: 0,
  pageSize: 36,
  pageFetchSize: 240,
  pageCursor: null,
  hasMorePages: false,
  loadingPage: false,
  thumbObserver: null,
  syncing: false,
  retitling: false,
  livePollTimer: null,
  livePolling: false,
  livePollSeconds: 8,
  liveRecentLimit: 120,
  latestMessageId: 0,
  aiTitledCount: 0,
  viewerIndex: -1,
  touchStartX: 0,
  touchStartY: 0,
  searchDebounceTimer: null,
  isMobile: window.matchMedia("(max-width: 768px)").matches,
  isTouch: "ontouchstart" in window || navigator.maxTouchPoints > 0,
};

// DOM elements cache
const elements = {};

// Initialize element references
function initElements() {
  const ids = [
    "sessionText", "syncBtn", "retitleBtn", "toTopBtn", "loadMoreBtn",
    "searchInput", "sortSelect", "layoutDenseBtn", "layoutComfortBtn",
    "countText", "syncText", "aiStatusText", "statTotal", "statVideos",
    "statImages", "statSize", "grid", "emptyState", "cardTemplate",
    "viewer", "viewerMedia", "viewerInfo", "viewerInfoPanel", "sheetGrip",
    "viewerTitle", "viewerDescription", "viewerCaption", "aiInsightsPanel",
    "aiInsightsContent", "viewerType", "viewerSize", "viewerDate", "viewerResolution",
    "viewerDownload", "viewerCopyLink", "viewerCopyEmbed", "viewerPrev",
    "viewerNext", "closeViewer", "toastContainer"
  ];
  
  ids.forEach(id => {
    elements[id] = document.getElementById(id);
  });
  
  elements.tabs = Array.from(document.querySelectorAll(".tab"));
}

// Utility: Copy to clipboard with visual feedback
async function copyToClipboard(text) {
  const value = String(text || "");
  if (!value) return false;
  
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(value);
      showToast("Copied to clipboard!", "success");
      return true;
    }
  } catch (_) {}

  try {
    const ta = document.createElement("textarea");
    ta.value = value;
    ta.setAttribute("readonly", "true");
    ta.style.cssText = "position:fixed;left:-9999px;opacity:0;";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    if (ok) showToast("Copied to clipboard!", "success");
    return Boolean(ok);
  } catch (_) {
    showToast("Copy failed", "error");
    return false;
  }
}

// Toast notification system
function showToast(message, type = "info", duration = 3000) {
  const container = elements.toastContainer;
  if (!container) return;
  
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.setAttribute("role", "status");
  toast.setAttribute("aria-live", "polite");
  
  const icons = {
    success: "✓",
    error: "✕",
    info: "ℹ",
    ai: "✨"
  };
  
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.info}</span>
    <span class="toast-message">${message}</span>
  `;
  
  container.appendChild(toast);
  
  // Trigger animation
  requestAnimationFrame(() => {
    toast.classList.add("show");
  });
  
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, duration);
  
  callHaptic("light");
}

// Format utilities
function fmtBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes <= 0) return "0 MB";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = bytes;
  let i = 0;
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024;
    i += 1;
  }
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function fmtRelative(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unknown";
  const delta = Math.floor((Date.now() - d.getTime()) / 1000);
  if (delta < 60) return "just now";
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  if (delta < 604800) return `${Math.floor(delta / 86400)}d ago`;
  return d.toLocaleDateString();
}

function fmtDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Unknown";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function fmtDuration(seconds) {
  const raw = Number(seconds) || 0;
  if (!Number.isFinite(raw) || raw <= 0) return "";
  const sec = Math.max(0, Math.floor(raw));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}

function resBadgeFor(item) {
  const w = Number(item.width) || 0;
  const h = Number(item.height) || 0;
  const maxSide = Math.max(w, h);
  if (maxSide >= 2160 || w >= 3840 || h >= 2160) return "4K";
  if (maxSide >= 1440) return "2K";
  if (maxSide >= 1080 || w >= 1920 || h >= 1080) return "HD";
  if (maxSide >= 720 || w >= 1280 || h >= 720) return "HD";
  return "";
}

function getResolutionText(item) {
  const w = Number(item.width) || 0;
  const h = Number(item.height) || 0;
  if (w && h) return `${w}×${h}`;
  return "";
}

// AI-powered title generation
function titleFor(item) {
  const aiTitle = (item.ai_title || "").trim();
  if (aiTitle) return aiTitle;
  const caption = (item.caption || "").trim();
  if (caption) return caption.split("\n")[0].substring(0, 60);
  const mid = item.message_id ? ` #${item.message_id}` : "";
  if (item.media_kind === "video") return `Video${mid}`;
  if (item.media_kind === "image") return `Image${mid}`;
  return item.file_name || `Media${mid}`;
}

// Check if item has AI enhancements
function hasAIEnhancement(item) {
  return !!(item.ai_title || item.ai_description);
}

// Generate AI insights for viewer
function generateAIInsights(item) {
  const insights = [];
  
  if (item.ai_title) {
    insights.push(`AI-generated title: "${item.ai_title}"`);
  }
  
  if (item.ai_description) {
    const desc = item.ai_description;
    const keywords = extractKeywords(desc);
    if (keywords.length > 0) {
      insights.push(`Detected themes: ${keywords.join(", ")}`);
    }
  }
  
  if (item.media_kind === "video" && item.duration) {
    const duration = Number(item.duration);
    if (duration < 30) insights.push("Short-form content");
    else if (duration > 300) insights.push("Long-form content");
  }
  
  const size = Number(item.size) || 0;
  if (size > 100 * 1024 * 1024) insights.push("High-quality file");
  
  const w = Number(item.width) || 0;
  if (w >= 1920) insights.push("High resolution");
  
  return insights;
}

// Simple keyword extraction for AI insights
function extractKeywords(text) {
  if (!text) return [];
  const commonWords = new Set(["the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"]);
  const words = text.toLowerCase().match(/\b\w{4,}\b/g) || [];
  const freq = {};
  words.forEach(w => {
    if (!commonWords.has(w)) freq[w] = (freq[w] || 0) + 1;
  });
  return Object.entries(freq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([w]) => w.charAt(0).toUpperCase() + w.slice(1));
}

function asTime(iso) {
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
}

// Haptic feedback
function callHaptic(kind = "light") {
  if (!tg || !tg.HapticFeedback) return;
  try {
    tg.HapticFeedback.impactOccurred(kind);
  } catch (_) {}
}

function callNotification(type = "success") {
  if (!tg || !tg.HapticFeedback) return;
  try {
    tg.HapticFeedback.notificationOccurred(type);
  } catch (_) {}
}

// API helpers
function requestHeaders() {
  const headers = {
    "Content-Type": "application/json",
  };
  if (state.initData) {
    headers["X-Telegram-Init-Data"] = state.initData;
  }
  return headers;
}

function setSessionText(message) {
  if (elements.sessionText) {
    elements.sessionText.textContent = message;
  }
}

// Context fetching with retry
async function fetchContext(retries = 2) {
  for (let i = 0; i <= retries; i++) {
    try {
      const res = await fetch("/api/webapp/context", {
        headers: requestHeaders(),
        cache: "no-store",
      });

      if (!res.ok) throw new Error("Failed to get webapp context");

      state.context = await res.json();

      if (state.context.is_telegram_webapp) {
        const user = state.context.payload?.user;
        const uname = user ? (user.username ? `@${user.username}` : user.first_name || "User") : "User";
        const verify = state.context.verified ? "✓" : "○";
        setSessionText(`${uname} ${verify} Telegram Mini App`);
      } else {
        setSessionText("Browser Mode");
      }
      return;
    } catch (err) {
      if (i === retries) throw err;
      await new Promise(r => setTimeout(r, 500 * (i + 1)));
    }
  }
}

// Statistics rendering with animation
function renderStats() {
  const s = state.stats && Number(state.stats.total) ? state.stats : null;
  const total = s ? Number(s.total) || 0 : state.items.length;
  const videos = s ? Number(s.videos) || 0 : state.items.filter(x => x.media_kind === "video").length;
  const images = s ? Number(s.images) || 0 : total - videos;
  const size = s ? Number(s.bytes) || 0 : state.items.reduce((sum, x) => sum + (Number(x.size) || 0), 0);

  animateValue(elements.statTotal, total);
  animateValue(elements.statVideos, videos);
  animateValue(elements.statImages, images);
  if (elements.statSize) elements.statSize.textContent = fmtBytes(size);
}

function animateValue(element, target) {
  if (!element) return;
  const start = parseInt(element.textContent) || 0;
  if (start === target) return;
  
  const duration = 600;
  const startTime = performance.now();
  
  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeProgress = 1 - Math.pow(1 - progress, 3);
    const current = Math.floor(start + (target - start) * easeProgress);
    element.textContent = current.toLocaleString();
    
    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }
  
  requestAnimationFrame(update);
}

function updateMetaRow() {
  const showing = Math.min(state.visibleCount, state.filtered.length);
  let status = state.syncAt ? `Synced ${fmtRelative(state.syncAt)}` : "Not synced";
  if (state.sessionMode) status += ` · ${state.sessionMode}`;
  
  const total = Number(state.stats?.total) || 0;
  const totalText = total > 0 ? ` · Total ${total.toLocaleString()}` : "";
  
  if (elements.countText) {
    elements.countText.textContent = `Showing ${showing.toLocaleString()} of ${state.filtered.length.toLocaleString()}${totalText}`;
  }
  if (elements.syncText) elements.syncText.textContent = status;
  
  // Update AI status
  if (elements.aiStatusText) {
    const aiCount = state.items.filter(hasAIEnhancement).length;
    if (aiCount > 0) {
      elements.aiStatusText.textContent = `✨ ${aiCount} AI enhanced`;
      elements.aiStatusText.classList.remove("hidden");
    } else {
      elements.aiStatusText.classList.add("hidden");
    }
  }
}

// Enhanced sorting with AI option
function applySort(items) {
  const list = [...items];
  if (state.sort === "oldest") {
    list.sort((a, b) => asTime(a.date) - asTime(b.date));
  } else if (state.sort === "largest") {
    list.sort((a, b) => (Number(b.size) || 0) - (Number(a.size) || 0));
  } else if (state.sort === "ai") {
    list.sort((a, b) => {
      const aHasAI = hasAIEnhancement(a) ? 1 : 0;
      const bHasAI = hasAIEnhancement(b) ? 1 : 0;
      if (aHasAI !== bHasAI) return bHasAI - aHasAI;
      return asTime(b.date) - asTime(a.date);
    });
  } else {
    list.sort((a, b) => asTime(b.date) - asTime(a.date));
  }
  return list;
}

// Enhanced filtering with AI search
function applyFilter(resetVisible = true) {
  const q = state.search.trim().toLowerCase();
  let items = state.items;

  if (state.filter !== "all") {
    items = items.filter(item => item.media_kind === state.filter);
  }

  if (q) {
    items = items.filter(item => {
      const searchFields = [
        item.ai_title,
        item.ai_description,
        item.caption,
        item.file_name,
        item.media_kind,
      ].filter(Boolean).join(" ").toLowerCase();
      return searchFields.includes(q);
    });
  }

  state.filtered = applySort(items);
  if (resetVisible) {
    state.visibleCount = Math.min(state.pageSize, state.filtered.length);
  } else {
    state.visibleCount = Math.min(Math.max(state.visibleCount, state.pageSize), state.filtered.length);
  }
  renderGrid();
}

// Intersection Observer for lazy loading
function ensureObserver() {
  if (state.thumbObserver) {
    state.thumbObserver.disconnect();
  }
  state.thumbObserver = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        const src = el.dataset.src;
        if (!src) {
          state.thumbObserver.unobserve(el);
          return;
        }
        el.src = src;
        state.thumbObserver.unobserve(el);
      });
    },
    {
      root: null,
      rootMargin: "300px 0px",
      threshold: 0.01,
    }
  );
}

function wireThumbMedia(item, thumb, mediaSlot) {
  const isVideo = item.media_kind === "video";
  const fallbackSrc = "/assets/video-placeholder.svg";
  const src = isVideo ? (item.thumb_url || fallbackSrc) : item.url;
  const media = document.createElement("img");
  media.className = "thumb-media";
  media.dataset.src = src;
  media.alt = titleFor(item);
  media.loading = "lazy";
  media.decoding = "async";

  const finish = () => thumb.classList.add("loaded");
  media.addEventListener("load", finish, { once: true });
  media.addEventListener(
    "error",
    () => {
      if (isVideo && media.src !== fallbackSrc) {
        media.src = fallbackSrc;
        return;
      }
      finish();
    },
    { once: true }
  );

  mediaSlot.appendChild(media);
  if (state.thumbObserver) state.thumbObserver.observe(media);
}

function updateLoadMoreButton() {
  const canReveal = state.visibleCount < state.filtered.length;
  const canFetch = !canReveal && state.hasMorePages;
  const shouldShow = canReveal || canFetch;
  
  if (elements.loadMoreBtn) {
    elements.loadMoreBtn.classList.toggle("hidden", !shouldShow);
    elements.loadMoreBtn.disabled = state.loadingPage || state.syncing;
    elements.loadMoreBtn.textContent = state.loadingPage 
      ? "Loading..." 
      : canFetch 
        ? "Load Older" 
        : "Load More";
  }
}

// Grid rendering with AI indicators
function renderGrid() {
  if (!elements.grid) return;
  elements.grid.innerHTML = "";

  if (!state.filtered.length) {
    if (elements.emptyState) elements.emptyState.classList.remove("hidden");
    updateMetaRow();
    updateLoadMoreButton();
    return;
  }

  if (elements.emptyState) elements.emptyState.classList.add("hidden");
  ensureObserver();

  const visibleItems = state.filtered.slice(0, state.visibleCount);
  const fragment = document.createDocumentFragment();

  visibleItems.forEach((item, idx) => {
    const node = elements.cardTemplate.content.firstElementChild.cloneNode(true);
    const isAI = hasAIEnhancement(item);
    
    node.style.setProperty("--delay", `${Math.min((idx % 20) * 25, 400)}ms`);
    node.classList.toggle("kind-video", item.media_kind === "video");
    node.classList.toggle("kind-image", item.media_kind !== "video");
    node.classList.toggle("ai-enhanced", isAI);

    const button = node.querySelector(".card-btn");
    const thumb = node.querySelector(".thumb");
    const mediaSlot = node.querySelector(".media-slot");
    const kindBadge = node.querySelector(".badge-kind");
    const cacheBadge = node.querySelector(".badge-cache");
    const resBadge = node.querySelector(".badge-res");
    const durationBadge = node.querySelector(".badge-duration");
    const title = node.querySelector(".card-title");
    const subtitle = node.querySelector(".card-subtitle");

    wireThumbMedia(item, thumb, mediaSlot);

    kindBadge.textContent = item.media_kind === "video" ? "VIDEO" : "IMAGE";
    cacheBadge.textContent = item.is_cached ? "CACHED" : "STREAM";
    cacheBadge.classList.add(item.is_cached ? "cached" : "stream");

    if (resBadge) resBadge.textContent = item.media_kind === "video" ? resBadgeFor(item) : "";
    if (durationBadge) {
      durationBadge.textContent = item.media_kind === "video" ? fmtDuration(item.duration) : "";
    }

    title.textContent = titleFor(item);
    const desc = String(item.ai_description || "").trim();
    subtitle.textContent = desc || `${fmtBytes(item.size)} · ${fmtRelative(item.date)}${item.is_cached ? "" : " · stream"}`;

    button.addEventListener("click", () => openViewer(item));
    fragment.appendChild(node);
  });

  elements.grid.appendChild(fragment);
  updateMetaRow();
  updateLoadMoreButton();
}

// Viewer functionality with touch support
function setViewerIndexForItem(item) {
  const id = Number(item?.message_id) || 0;
  if (!id || !Array.isArray(state.filtered) || !state.filtered.length) {
    state.viewerIndex = -1;
    return;
  }
  const idx = state.filtered.findIndex(x => Number(x.message_id) === id);
  state.viewerIndex = idx >= 0 ? idx : -1;
}

function updateViewerNav() {
  if (!elements.viewerPrev || !elements.viewerNext) return;
  const idx = Number(state.viewerIndex);
  const has = Array.isArray(state.filtered) && state.filtered.length > 0 && idx >= 0;
  elements.viewerPrev.disabled = !(has && idx > 0);
  elements.viewerNext.disabled = !(has && idx < state.filtered.length - 1);
}

function openViewerByIndex(index) {
  const idx = Number(index);
  if (!Number.isFinite(idx) || idx < 0 || idx >= state.filtered.length) return;
  state.viewerIndex = idx;
  openViewer(state.filtered[idx], false);
}

function openViewer(item, recomputeIndex = true) {
  if (!elements.viewerMedia) return;
  
  elements.viewerMedia.innerHTML = "";
  const fullUrl = new URL(item.url, window.location.origin).toString();

  if (recomputeIndex) setViewerIndexForItem(item);
  updateViewerNav();

  if (item.media_kind === "video") {
    const video = document.createElement("video");
    video.src = item.url;
    video.controls = true;
    video.autoplay = true;
    video.playsInline = true;
    video.preload = "metadata";
    video.setAttribute("playsinline", "");
    video.setAttribute("webkit-playsinline", "");
    elements.viewerMedia.appendChild(video);
  } else {
    const img = document.createElement("img");
    img.src = item.url;
    img.alt = titleFor(item);
    img.loading = "eager";
    elements.viewerMedia.appendChild(img);
  }

  if (elements.viewerInfo) {
    elements.viewerInfo.classList.remove("expanded");
  }
  
  if (elements.viewerTitle) elements.viewerTitle.textContent = titleFor(item);
  if (elements.viewerDescription) {
    elements.viewerDescription.textContent = (item.ai_description || "").trim() || "No AI description available";
  }
  if (elements.viewerCaption) {
    elements.viewerCaption.textContent = item.caption || "No caption";
  }
  if (elements.viewerType) elements.viewerType.textContent = item.media_kind.toUpperCase();
  if (elements.viewerSize) elements.viewerSize.textContent = fmtBytes(item.size);
  if (elements.viewerDate) elements.viewerDate.textContent = fmtDate(item.date);
  
  if (elements.viewerResolution) {
    const res = getResolutionText(item);
    elements.viewerResolution.textContent = res || "";
    elements.viewerResolution.classList.toggle("hidden", !res);
  }

  // Update AI insights
  if (elements.aiInsightsPanel && elements.aiInsightsContent) {
    const insights = generateAIInsights(item);
    if (insights.length > 0) {
      elements.aiInsightsContent.innerHTML = insights.map(i => `<p>• ${i}</p>`).join("");
      elements.aiInsightsPanel.classList.remove("hidden");
    } else {
      elements.aiInsightsPanel.classList.add("hidden");
    }
  }

  if (elements.viewerDownload) {
    elements.viewerDownload.href = item.url;
    elements.viewerDownload.setAttribute("download", item.file_name || "media");
  }

  if (elements.viewerCopyLink) {
    elements.viewerCopyLink.onclick = async () => {
      await copyToClipboard(fullUrl);
      callHaptic("light");
    };
  }

  if (elements.viewerCopyEmbed) {
    elements.viewerCopyEmbed.onclick = async () => {
      const title = titleFor(item).replace(/"/g, "");
      const snippet = item.media_kind === "video"
        ? `<video src="${fullUrl}" controls playsinline></video>`
        : `<img src="${fullUrl}" alt="${title}" loading="lazy">`;
      await copyToClipboard(snippet);
      callHaptic("light");
    };
  }

  if (elements.viewer) {
    elements.viewer.classList.remove("hidden");
    elements.viewer.setAttribute("aria-hidden", "false");
  }
  document.body.style.overflow = "hidden";

  if (tg && tg.BackButton) tg.BackButton.show();
  callHaptic("medium");
}

function closeViewer() {
  if (elements.viewer) {
    elements.viewer.classList.add("hidden");
    elements.viewer.setAttribute("aria-hidden", "true");
  }
  if (elements.viewerMedia) elements.viewerMedia.innerHTML = "";
  document.body.style.overflow = "";
  state.viewerIndex = -1;
  if (elements.viewerInfo) elements.viewerInfo.classList.remove("expanded");
  if (tg && tg.BackButton) tg.BackButton.hide();
}

function navigateViewer(direction) {
  if (state.viewerIndex < 0) return;
  const newIndex = state.viewerIndex + direction;
  if (newIndex >= 0 && newIndex < state.filtered.length) {
    openViewerByIndex(newIndex);
    callHaptic("light");
  }
}

// Touch gesture handling
function initTouchGestures() {
  if (!state.isTouch || !elements.viewer) return;
  
  let startX = 0;
  let startY = 0;
  let startTime = 0;
  
  elements.viewer.addEventListener("touchstart", (e) => {
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
    startTime = Date.now();
  }, { passive: true });
  
  elements.viewer.addEventListener("touchend", (e) => {
    if (!startX || !startY) return;
    
    const endX = e.changedTouches[0].clientX;
    const endY = e.changedTouches[0].clientY;
    const diffX = startX - endX;
    const diffY = startY - endY;
    const duration = Date.now() - startTime;
    
    // Swipe threshold
    const threshold = 50;
    const velocity = Math.abs(diffX) / duration;
    
    // Horizontal swipe for navigation
    if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > threshold && velocity > 0.3) {
      if (diffX > 0) {
        navigateViewer(1); // Swipe left -> next
      } else {
        navigateViewer(-1); // Swipe right -> prev
      }
    }
    
    // Vertical swipe to close on mobile
    if (state.isMobile && Math.abs(diffY) > Math.abs(diffX) && diffY > threshold * 2) {
      closeViewer();
    }
    
    startX = 0;
    startY = 0;
  }, { passive: true });
  
  // Double tap to zoom (simplified - just logs for now)
  let lastTap = 0;
  elements.viewerMedia?.addEventListener("touchend", (e) => {
    const currentTime = Date.now();
    if (currentTime - lastTap < 300) {
      // Double tap detected
      callHaptic("medium");
    }
    lastTap = currentTime;
  });
}

// Data normalization
function normalizeItems(items) {
  return items.map(item => {
    const isCached = typeof item.is_cached === "boolean" 
      ? item.is_cached 
      : String(item.url || "").startsWith("/media/");
    const thumbUrl = item.thumb_url || (item.media_kind === "image" ? item.url : "/assets/video-placeholder.svg");
    return {
      ...item,
      is_cached: isCached,
      thumb_url: thumbUrl,
      ai_title: item.ai_title || "",
      ai_description: item.ai_description || "",
    };
  });
}

function applyApiPayload(data, resetVisible = true) {
  state.items = Array.isArray(data.items) ? normalizeItems(data.items) : [];
  state.syncAt = data.synced_at || null;
  state.syncError = data.sync_error || null;
  state.sessionMode = data.session_mode || null;
  
  if (data?.stats && typeof data.stats === "object") {
    state.stats = {
      total: Number(data.stats.total) || 0,
      videos: Number(data.stats.videos) || 0,
      images: Number(data.stats.images) || 0,
      bytes: Number(data.stats.bytes) || 0,
    };
  }
  
  state.latestMessageId = Number(data.latest_message_id) || 
    (state.items.length ? Number(state.items[0].message_id) || 0 : 0);
  state.aiTitledCount = Number(data.ai_titled_count) || 0;
  state.pageCursor = data?.next_before 
    ? Number(data.next_before) || null 
    : (state.items.length ? Number(state.items[state.items.length - 1].message_id) || null : null);
  state.hasMorePages = Boolean(data?.has_more);
  state.loadingPage = false;

  renderStats();
  applyFilter(resetVisible);

  if (state.syncError) {
    showToast(state.syncError, "error");
  } else if (data?.sync_notice) {
    showToast(data.sync_notice, "info");
  }
}

// API calls
async function loadMedia() {
  const url = `/api/media/page?limit=${state.pageFetchSize}`;
  const res = await fetch(url, {
    headers: requestHeaders(),
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Failed to load media");
  }

  const data = await res.json();
  applyApiPayload(data, true);
}

function mergeRecentPayload(data) {
  const incoming = Array.isArray(data.items) ? normalizeItems(data.items) : [];
  if (!incoming.length) {
    state.syncAt = data.synced_at || state.syncAt;
    updateMetaRow();
    return;
  }

  const map = new Map();
  state.items.forEach(item => {
    const id = Number(item.message_id) || 0;
    if (id > 0) map.set(id, item);
  });

  incoming.forEach(item => {
    const id = Number(item.message_id) || 0;
    if (id <= 0) return;
    const prev = map.get(id);
    map.set(id, prev ? { ...prev, ...item } : item);
  });

  state.items = Array.from(map.values());
  state.items.sort((a, b) => {
    const byDate = asTime(b.date) - asTime(a.date);
    if (byDate !== 0) return byDate;
    return (Number(b.message_id) || 0) - (Number(a.message_id) || 0);
  });

  const incomingLatest = Number(data.latest_message_id) || 0;
  const localLatest = state.items.length ? Number(state.items[0].message_id) || 0 : 0;
  state.latestMessageId = Math.max(state.latestMessageId, incomingLatest, localLatest);
  state.aiTitledCount = Number(data.ai_titled_count) || state.aiTitledCount;
  state.syncAt = data.synced_at || state.syncAt;
  state.sessionMode = data.session_mode || state.sessionMode;
  state.syncError = data.sync_error || null;
  
  if (data?.stats && typeof data.stats === "object") {
    state.stats = {
      total: Number(data.stats.total) || 0,
      videos: Number(data.stats.videos) || 0,
      images: Number(data.stats.images) || 0,
      bytes: Number(data.stats.bytes) || 0,
    };
  }

  renderStats();
  applyFilter(false);
}

function mergePagePayload(data) {
  const incoming = Array.isArray(data.items) ? normalizeItems(data.items) : [];
  if (!incoming.length) {
    state.syncAt = data.synced_at || state.syncAt;
    state.sessionMode = data.session_mode || state.sessionMode;
    if (data?.stats && typeof data.stats === "object") {
      state.stats = {
        total: Number(data.stats.total) || 0,
        videos: Number(data.stats.videos) || 0,
        images: Number(data.stats.images) || 0,
        bytes: Number(data.stats.bytes) || 0,
      };
    }
    state.hasMorePages = Boolean(data?.has_more);
    state.pageCursor = data?.next_before ? Number(data.next_before) || state.pageCursor : state.pageCursor;
    renderStats();
    updateMetaRow();
    updateLoadMoreButton();
    return;
  }

  const map = new Map();
  state.items.forEach(item => {
    const id = Number(item.message_id) || 0;
    if (id > 0) map.set(id, item);
  });
  incoming.forEach(item => {
    const id = Number(item.message_id) || 0;
    if (id > 0) map.set(id, item);
  });

  state.items = Array.from(map.values());
  state.items.sort((a, b) => {
    const byDate = asTime(b.date) - asTime(a.date);
    if (byDate !== 0) return byDate;
    return (Number(b.message_id) || 0) - (Number(a.message_id) || 0);
  });

  state.syncAt = data.synced_at || state.syncAt;
  state.sessionMode = data.session_mode || state.sessionMode;
  state.syncError = data.sync_error || null;
  state.latestMessageId = Math.max(state.latestMessageId, Number(data.latest_message_id) || 0);
  state.aiTitledCount = Number(data.ai_titled_count) || state.aiTitledCount;
  
  if (data?.stats && typeof data.stats === "object") {
    state.stats = {
      total: Number(data.stats.total) || 0,
      videos: Number(data.stats.videos) || 0,
      images: Number(data.stats.images) || 0,
      bytes: Number(data.stats.bytes) || 0,
    };
  }
  state.pageCursor = data?.next_before ? Number(data.next_before) || state.pageCursor : state.pageCursor;
  state.hasMorePages = Boolean(data?.has_more);

  renderStats();
  applyFilter(false);
}

async function fetchNextPage() {
  if (!state.pageCursor) return;
  const res = await fetch(`/api/media/page?limit=${state.pageFetchSize}&before=${state.pageCursor}`, {
    headers: requestHeaders(),
    cache: "no-store",
  });
  if (!res.ok) return;
  const data = await res.json();
  mergePagePayload(data);
}

async function pollRecentMedia() {
  if (state.livePolling || state.syncing) return;
  state.livePolling = true;

  try {
    const res = await fetch(`/api/media/recent?limit=${state.liveRecentLimit}`, {
      headers: requestHeaders(),
      cache: "no-store",
    });
    if (!res.ok) return;

    const data = await res.json();
    const incomingLatest = Number(data.latest_message_id) || 0;
    const incomingTotal = Number(data.total) || 0;
    const incomingAiCount = Number(data.ai_titled_count) || 0;
    const localTotal = Number(state.stats?.total) || state.items.length;
    
    const shouldMerge = incomingLatest > state.latestMessageId ||
      incomingTotal > localTotal ||
      incomingAiCount !== state.aiTitledCount;

    if (shouldMerge) {
      mergeRecentPayload(data);
      if (incomingLatest > state.latestMessageId) {
        showToast("New media available!", "success");
      }
    } else {
      state.syncAt = data.synced_at || state.syncAt;
      updateMetaRow();
    }
  } catch (error) {
    console.error("Live update poll failed", error);
  } finally {
    state.livePolling = false;
  }
}

async function startLiveUpdates() {
  try {
    const res = await fetch("/api/health", {
      headers: requestHeaders(),
      cache: "no-store",
    });
    if (res.ok) {
      const health = await res.json();
      const sec = Number(health.live_sync_seconds);
      const lim = Number(health.live_sync_limit);
      if (Number.isFinite(sec) && sec > 0) state.livePollSeconds = Math.max(5, Math.floor(sec));
      if (Number.isFinite(lim) && lim > 0) state.liveRecentLimit = Math.max(20, Math.min(500, Math.floor(lim)));
    }
  } catch (_) {}

  if (state.livePollTimer) clearInterval(state.livePollTimer);

  state.livePollTimer = window.setInterval(() => {
    void pollRecentMedia();
  }, state.livePollSeconds * 1000);

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") void pollRecentMedia();
  });
}

// UI state helpers
function setSyncButtonLoading(isLoading) {
  state.syncing = isLoading;
  if (elements.syncBtn) {
    elements.syncBtn.disabled = isLoading;
    elements.syncBtn.innerHTML = isLoading ? `<span>Syncing...</span>` : `<span>Sync</span>`;
  }
}

function setRetitleButtonLoading(isLoading) {
  state.retitling = isLoading;
  if (elements.retitleBtn) {
    elements.retitleBtn.disabled = isLoading;
    elements.retitleBtn.innerHTML = isLoading ? `<span>Processing...</span>` : `<span>AI</span>`;
  }
}

// Actions
async function syncNow() {
  setSyncButtonLoading(true);
  try {
    showToast("Syncing media from Telegram...", "info");
    const res = await fetch(`/api/sync?limit=all&response_limit=${state.pageFetchSize}&wait_seconds=3`, {
      method: "POST",
      headers: requestHeaders(),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "Sync failed");
    }
    const data = await res.json();
    applyApiPayload(data, true);
    showToast(`Synced ${data.items?.length || 0} items!`, "success");
    callNotification("success");
  } catch (error) {
    console.error(error);
    showToast(error.message || "Sync failed", "error");
    callNotification("error");
  } finally {
    setSyncButtonLoading(false);
  }
}

async function improveTitles() {
  setRetitleButtonLoading(true);
  try {
    showToast("AI is analyzing content...", "ai");
    const res = await fetch(`/api/ai-titles?mode=style&recent_limit=0&batch_size=25`, {
      method: "POST",
      headers: requestHeaders(),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "AI enhancement failed");
    }
    const data = await res.json();
    if (data?.ai_titled_count !== undefined) {
      state.aiTitledCount = Number(data.ai_titled_count) || state.aiTitledCount;
    }
    if (data?.timed_out) {
      showToast("AI processing in background...", "info");
    } else if (data?.generated > 0) {
      showToast(`AI enhanced ${data.generated} items!`, "success");
    } else {
      showToast("AI analysis complete", "success");
    }
    void pollRecentMedia();
    callNotification("success");
  } catch (error) {
    console.error(error);
    showToast(error.message || "AI enhancement failed", "error");
    callNotification("error");
  } finally {
    setRetitleButtonLoading(false);
  }
}

async function loadMore() {
  if (state.visibleCount < state.filtered.length) {
    state.visibleCount = Math.min(state.visibleCount + state.pageSize, state.filtered.length);
    renderGrid();
    return;
  }

  if (!state.hasMorePages || state.loadingPage || state.syncing) return;
  if (!state.pageCursor) return;

  state.loadingPage = true;
  updateLoadMoreButton();
  try {
    await fetchNextPage();
  } finally {
    state.loadingPage = false;
    updateLoadMoreButton();
  }
}

// Mini App integration
function setupMiniAppChrome() {
  if (!tg) return;
  
  try {
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#0a0f14");
    tg.setBackgroundColor("#0a0f14");
    
    // Enable swipe to close if supported
    if (tg.enableClosingConfirmation) {
      tg.enableClosingConfirmation();
    }
  } catch (_) {}

  if (tg.BackButton) {
    tg.BackButton.onClick(() => {
      if (!elements.viewer?.classList.contains("hidden")) {
        closeViewer();
      }
    });
  }

  if (tg.MainButton) {
    tg.MainButton.setText("SYNC MEDIA");
    tg.MainButton.setParams({ color: "#ff3b30", text_color: "#ffffff" });
    tg.MainButton.onClick(async () => {
      try {
        await syncNow();
      } catch (error) {
        console.error(error);
      }
    });
    tg.MainButton.show();
  }
}

// Layout management
function getStoredDensity() {
  try {
    const v = localStorage.getItem("twa_density");
    return v === "comfort" ? "comfort" : "dense";
  } catch (_) {
    return "dense";
  }
}

function setDensity(next) {
  const density = next === "comfort" ? "comfort" : "dense";
  state.density = density;
  document.documentElement.dataset.density = density;

  if (elements.layoutDenseBtn) {
    elements.layoutDenseBtn.setAttribute("aria-pressed", density === "dense" ? "true" : "false");
  }
  if (elements.layoutComfortBtn) {
    elements.layoutComfortBtn.setAttribute("aria-pressed", density === "comfort" ? "true" : "false");
  }

  try {
    localStorage.setItem("twa_density", density);
  } catch (_) {}

  renderGrid();
}

// Debounced search
function debouncedSearch(value) {
  if (state.searchDebounceTimer) clearTimeout(state.searchDebounceTimer);
  state.searchDebounceTimer = setTimeout(() => {
    state.search = value;
    applyFilter(true);
  }, 200);
}

// Event binding
function bindUI() {
  // Search with debouncing
  elements.searchInput?.addEventListener("input", (ev) => {
    debouncedSearch(ev.target.value);
  });

  // Layout toggles
  elements.layoutDenseBtn?.addEventListener("click", () => {
    setDensity("dense");
    callHaptic("light");
  });
  elements.layoutComfortBtn?.addEventListener("click", () => {
    setDensity("comfort");
    callHaptic("light");
  });

  // Filter tabs with keyboard navigation
  elements.tabs?.forEach((tab, index) => {
    tab.addEventListener("click", () => {
      elements.tabs.forEach(t => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
        t.setAttribute("tabindex", "-1");
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      tab.setAttribute("tabindex", "0");
      state.filter = tab.dataset.filter;
      applyFilter(true);
      callHaptic("light");
    });
    
    // Keyboard navigation
    tab.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight") {
        const next = elements.tabs[index + 1] || elements.tabs[0];
        next.focus();
        next.click();
      } else if (e.key === "ArrowLeft") {
        const prev = elements.tabs[index - 1] || elements.tabs[elements.tabs.length - 1];
        prev.focus();
        prev.click();
      }
    });
  });

  // Sort
  elements.sortSelect?.addEventListener("change", (ev) => {
    state.sort = ev.target.value;
    applyFilter(true);
  });

  // Actions
  elements.syncBtn?.addEventListener("click", async () => {
    try {
      await syncNow();
    } catch (error) {
      console.error(error);
    }
  });

  elements.retitleBtn?.addEventListener("click", async () => {
    try {
      await improveTitles();
    } catch (error) {
      console.error(error);
    }
  });

  elements.loadMoreBtn?.addEventListener("click", () => {
    void loadMore();
  });

  elements.toTopBtn?.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
    callHaptic("light");
  });

  // Infinite scroll
  let scrollTimeout;
  window.addEventListener("scroll", () => {
    if (scrollTimeout) return;
    scrollTimeout = setTimeout(() => {
      scrollTimeout = null;
      const nearBottom = window.innerHeight + window.scrollY >= document.body.offsetHeight - 400;
      if (nearBottom && !state.syncing && !state.loadingPage) {
        void loadMore();
      }
    }, 100);
  }, { passive: true });

  // Viewer controls
  elements.closeViewer?.addEventListener("click", closeViewer);
  elements.viewer?.addEventListener("click", (event) => {
    if (event.target === elements.viewer || event.target.classList.contains("viewer-backdrop")) {
      closeViewer();
    }
  });

  elements.viewerPrev?.addEventListener("click", () => navigateViewer(-1));
  elements.viewerNext?.addEventListener("click", () => navigateViewer(1));

  // Sheet grip for mobile
  elements.sheetGrip?.addEventListener("click", () => {
    elements.viewerInfo?.classList.toggle("expanded");
    callHaptic("light");
  });

  // Keyboard navigation
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !elements.viewer?.classList.contains("hidden")) {
      closeViewer();
    }
    if (!elements.viewer?.classList.contains("hidden")) {
      if (event.key === "ArrowLeft") navigateViewer(-1);
      else if (event.key === "ArrowRight") navigateViewer(1);
    }
  });

  // Handle visibility change
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      // Refresh data when returning to app
      void pollRecentMedia();
    }
  });

  // Resize handler for responsive adjustments
  let resizeTimeout;
  window.addEventListener("resize", () => {
    if (resizeTimeout) clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      state.isMobile = window.matchMedia("(max-width: 768px)").matches;
    }, 250);
  });
}

// Bootstrap
async function bootstrap() {
  initElements();
  bindUI();
  setupMiniAppChrome();
  setDensity(getStoredDensity());
  initTouchGestures();

  try {
    await fetchContext();
    await loadMedia();
    await startLiveUpdates();
    showToast("Welcome to AfterDark Vault!", "info", 2000);
  } catch (error) {
    console.error(error);
    setSessionText("Connection failed");
    if (elements.emptyState) {
      elements.emptyState.classList.remove("hidden");
      elements.emptyState.innerHTML = `
        <div class="empty-icon">⚠️</div>
        <p>Failed to load media</p>
        <p style="font-size: 12px; margin-top: 8px;">Check your connection and try again</p>
        <button class="btn btn-primary" style="margin-top: 16px;" onclick="location.reload()">Retry</button>
      `;
    }
    showToast("Failed to initialize. Please refresh.", "error");
  }
}

// Start the app
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}
