// ============================================
// AFTERDARK - Gallery App
// ============================================

// Saved scroll position for viewer open/close
let _savedScrollY = 0;

// State
const state = {
  items: [],
  filtered: [],
  viewerIndex: -1,
  isLoading: false,
  isTouch: "ontouchstart" in window || navigator.maxTouchPoints > 0,
  totalItems: 0,
  loadedCount: 120,  // Load more items for faster experience
  renderBatchSize: 12,  // Render items in smaller batches for smoother scrolling
  renderedCount: 0,
  lazyObserver: null,
};

// Elements
const elements = {};

function initElements() {
  elements.grid = document.getElementById("grid");
  elements.emptyState = document.getElementById("emptyState");
  elements.loadMoreBtn = document.getElementById("loadMoreBtn");
  elements.searchInput = document.getElementById("searchInput");
  elements.syncBtn = document.getElementById("syncBtn");
  elements.chatFab = document.getElementById("chatFab");
  elements.chatPanel = document.getElementById("chatPanel");
  elements.chatMessages = document.getElementById("chatMessages");
  elements.chatInput = document.getElementById("chatInput");
  elements.chatSendBtn = document.getElementById("chatSendBtn");
  elements.retitleBtn = document.getElementById("retitleBtn");
  elements.sortSelect = document.getElementById("sortSelect");
  elements.toTopBtn = document.getElementById("toTopBtn");
  elements.layoutDenseBtn = document.getElementById("layoutDenseBtn");
  elements.layoutComfortBtn = document.getElementById("layoutComfortBtn");
  elements.loadingIndicator = document.getElementById("loadingIndicator");

  // Viewer
  elements.viewer = document.getElementById("viewer");
  elements.viewerMedia = document.getElementById("viewerMedia");
  elements.viewerTitle = document.getElementById("viewerTitle");
  elements.viewerDescription = document.getElementById("viewerDescription");
  elements.viewerCaption = document.getElementById("viewerCaption");
  elements.viewerType = document.getElementById("viewerType");
  elements.viewerSize = document.getElementById("viewerSize");
  elements.viewerDate = document.getElementById("viewerDate");
  elements.viewerResolution = document.getElementById("viewerResolution");
  elements.viewerDownload = document.getElementById("viewerDownload");
  elements.viewerCopyLink = document.getElementById("viewerCopyLink");
  elements.viewerPrev = document.getElementById("viewerPrev");
  elements.viewerNext = document.getElementById("viewerNext");
  elements.closeViewer = document.getElementById("closeViewer");
  elements.suggestedGrid = document.getElementById("suggestedGrid");
  elements.suggestedSection = document.getElementById("suggestedSection");

  // Stats
  elements.statTotal = document.getElementById("statTotal");
  elements.statVideos = document.getElementById("statVideos");
  elements.statImages = document.getElementById("statImages");
  elements.statSize = document.getElementById("statSize");
  elements.videoProgressBar = document.getElementById("videoProgressBar");
  elements.imageProgressBar = document.getElementById("imageProgressBar");
  elements.statVideoRatio = document.getElementById("statVideoRatio");
  elements.statImageRatio = document.getElementById("statImageRatio");
  elements.statAITitled = document.getElementById("statAITitled");
  elements.countText = document.getElementById("countText");
  elements.syncText = document.getElementById("syncText");
  elements.sessionText = document.getElementById("sessionText");
}

// ============================================
// Utility Functions
// ============================================

function fmtBytes(bytes) {
  if (!bytes) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function fmtDuration(seconds) {
  if (!seconds) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function fmtRelative(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  const now = new Date();
  const diff = now - date;
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor(diff / (1000 * 60 * 60));
  const minutes = Math.floor(diff / (1000 * 60));

  // Handle future dates or invalid dates
  if (isNaN(date.getTime()) || diff < 0) {
    return date.toLocaleDateString();
  }

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return date.toLocaleDateString();
}

function fmtDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString();
}

function titleFor(item) {
  return item.ai_title || item.caption || `${item.media_kind} #${item.message_id}`;
}

function hasAI(item) {
  return item.ai_title && !item.ai_title.includes("Video #") && !item.ai_title.includes("Image #");
}

function updateDashboardStats(stats, aiTitledCount) {
  const total = stats.total || 0;
  const videos = stats.videos || 0;
  const images = stats.images || 0;
  const aiTitled = aiTitledCount || 0;

  if (elements.statTotal) elements.statTotal.textContent = total.toLocaleString();
  if (elements.statVideos) elements.statVideos.textContent = videos.toLocaleString();
  if (elements.statImages) elements.statImages.textContent = images.toLocaleString();
  if (elements.statSize) elements.statSize.textContent = fmtBytes(stats.bytes || 0);

  if (total > 0) {
    const videoPct = Math.round((videos / total) * 100);
    const imagePct = Math.round((images / total) * 100);

    if (elements.videoProgressBar) elements.videoProgressBar.style.width = videoPct + "%";
    if (elements.imageProgressBar) elements.imageProgressBar.style.width = imagePct + "%";
    if (elements.statVideoRatio) elements.statVideoRatio.textContent = videoPct + "%";
    if (elements.statImageRatio) elements.statImageRatio.textContent = imagePct + "%";
  } else {
    if (elements.videoProgressBar) elements.videoProgressBar.style.width = "0%";
    if (elements.imageProgressBar) elements.imageProgressBar.style.width = "0%";
    if (elements.statVideoRatio) elements.statVideoRatio.textContent = "0%";
    if (elements.statImageRatio) elements.statImageRatio.textContent = "0%";
  }

  if (elements.statAITitled) elements.statAITitled.textContent = aiTitled.toLocaleString();
  if (elements.sessionText) elements.sessionText.textContent = `Vault: ${total} items`;
}

// ============================================
// Toast
// ============================================

function showToast(message, type = "info", duration = 3000) {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), duration);
}

// ============================================
// API
// ============================================

async function requestHeaders() {
  const headers = { "Content-Type": "application/json" };
  if (window.Telegram?.WebApp?.initData) {
    headers["X-Telegram-Init-Data"] = window.Telegram.WebApp.initData;
  }
  return headers;
}

async function fetchContext() {
  try {
    const res = await fetch(`/api/health?_=${Date.now()}`, {
      headers: await requestHeaders(),
      cache: 'no-store'
    });
    const data = await res.json();
    updateDashboardStats(data.stats || {}, data.ai_titled_count || 0);
    return data;
  } catch (error) {
    console.error("Failed to fetch context:", error);
    return null;
  }
}

async function loadMedia(limit = "all", offset = 0, refresh = false) {
  try {
    state.isLoading = true;
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (refresh) params.set("refresh", "true");
    params.set("_", String(Date.now()));  // Cache busting
    console.log("loadMedia: fetching with params", params.toString());
    const res = await fetch(`/api/media?${params}`, {
      headers: await requestHeaders(),
      cache: 'no-store'
    });

    if (!res.ok) {
      const errText = await res.text();
      console.error("API error:", res.status, errText);
      showToast(`Error ${res.status}: ${res.statusText}`, "error");
      return null;
    }

    const data = await res.json();
    console.log("API response:", data.items?.length, "items, total:", data.total, "stats:", data.stats);

    if (!data.items || data.items.length === 0) {
      console.log("No items returned from API");
      state.items = [];
      state.filtered = [];
      updateUI();
      return data;
    }

    // Store total for pagination
    state.totalItems = data.total || 0;

    if (offset === 0) {
      state.items = data.items || [];
      console.log("state.items:", state.items.length);
      applyFilter();
      console.log("state.filtered:", state.filtered.length);
      updateUI();
    } else {
      // Deduplicate by message_id before appending
      const existingIds = new Set(state.items.map(item => item.message_id));
      const newItems = (data.items || []).filter(item => !existingIds.has(item.message_id));
      state.items = [...state.items, ...newItems];
      console.log("state.items:", state.items.length);
      applyFilter();
      console.log("state.filtered:", state.filtered.length);

      // Remove skeleton placeholders without wiping the grid
      document.querySelectorAll(".load-more-skeleton").forEach(el => el.remove());

      // Append only the new batch of cards (no full re-render)
      const prevCount = state.renderedCount;
      const nextEnd = Math.min(prevCount + newItems.length, state.filtered.length);
      renderBatch(prevCount, nextEnd);
      updateLoadMoreButton();
    }

    const total = data.total || state.totalItems || 0;
    const loaded = state.items.length;

    if (elements.countText) elements.countText.textContent = `${loaded} of ${total} items`;
    if (elements.syncText) elements.syncText.textContent = data.synced_at ? `Synced: ${fmtRelative(data.synced_at)}` : '';

    updateDashboardStats(data.stats || {}, data.ai_titled_count || 0);

    return data;
  } catch (error) {
    console.error("Failed to load media:", error);
    showToast("Failed to load media", "error");
    return null;
  } finally {
    state.isLoading = false;
  }
}

// ============================================
// Filter & Sort
// ============================================

function applyFilter() {
  let items = [...state.items];

  console.log("applyFilter: starting with", items.length, "items");

  // Filter by type
  const activeFilter = document.querySelector(".tab.active")?.dataset.filter || "all";
  console.log("applyFilter: activeFilter =", activeFilter);

  if (activeFilter !== "all") {
    items = items.filter(item => item.media_kind === activeFilter);
    console.log("applyFilter: after type filter =", items.length);
  }

  // Search
  const search = (elements.searchInput?.value || "").toLowerCase().trim();
  if (search) {
    items = items.filter(item => {
      const title = (item.ai_title || "").toLowerCase();
      const desc = (item.ai_description || "").toLowerCase();
      const caption = (item.caption || "").toLowerCase();
      return title.includes(search) || desc.includes(search) || caption.includes(search);
    });
    console.log("applyFilter: after search filter =", items.length);
  }

  // Sort
  const sort = elements.sortSelect?.value || "newest";
  switch (sort) {
    case "newest":
      items.sort((a, b) => new Date(b.date) - new Date(a.date));
      break;
    case "oldest":
      items.sort((a, b) => new Date(a.date) - new Date(b.date));
      break;
    case "largest":
      items.sort((a, b) => (b.size || 0) - (a.size || 0));
      break;
    case "ai":
      items.sort((a, b) => (hasAI(b) ? 1 : 0) - (hasAI(a) ? 1 : 0));
      break;
  }

  state.filtered = items;
  console.log("applyFilter: final filtered =", state.filtered.length);
}

function updateUI() {
  renderGrid();
  updateLoadMoreButton();
}

function updateLoadMoreButton() {
  // Auto-load is enabled - hide the button and load automatically on scroll
  if (!elements.loadMoreBtn) return;

  // Hide the button - auto-loading is always on
  elements.loadMoreBtn.classList.add("hidden");
}

// ============================================
// Render
// ============================================

function renderGrid() {
  // Hide loading indicator
  if (elements.loadingIndicator) {
    elements.loadingIndicator.style.display = "none";
  }

  if (!elements.grid) {
    console.error("Grid element not found!");
    return;
  }

  elements.grid.innerHTML = "";
  state.renderedCount = 0;

  console.log("renderGrid: state.filtered.length =", state.filtered.length);

  if (state.filtered.length === 0) {
    elements.emptyState?.classList.remove("hidden");
    console.log("No items to render, showing empty state");
    return;
  }

  elements.emptyState?.classList.add("hidden");

  // Render all visible items
  renderBatch(0, Math.min(state.renderBatchSize, state.filtered.length));

  // Show load more button if there are more items
  updateLoadMoreButton();
}

// Render a batch of cards
function renderBatch(start, end) {
  const template = document.getElementById("cardTemplate");
  if (!template) {
    console.error("Card template not found!");
    return;
  }

  const fragment = document.createDocumentFragment();

  for (let index = start; index < end && index < state.filtered.length; index++) {
    const item = state.filtered[index];
    const card = template.content.cloneNode(true);
    const article = card.querySelector("article");

    article.dataset.index = index;
    if (hasAI(item)) article.classList.add("ai-enhanced");
    // Staggered fade-in for paginated cards
    if (start > 0) {
      article.classList.add("card-enter");
      article.style.animationDelay = `${(index - start) * 40}ms`;
    }

    // Use data-src for lazy loading
    const mediaSlot = card.querySelector(".media-slot");
    const thumbUrl = item.thumb_url || item.url;
    // Load first batch immediately, lazy load rest
    const isInitialBatch = index < 12;
    mediaSlot.innerHTML = `
      <img src="${thumbUrl}" alt="${titleFor(item)}" class="lazy-image" decoding="async" loading="${isInitialBatch ? 'eager' : 'lazy'}">
    `;

    const badge = card.querySelector(".badge-kind");
    badge.textContent = item.media_kind === "video" ? "VIDEO" : "IMAGE";
    badge.classList.add(item.media_kind);

    const duration = card.querySelector(".badge-duration");
    if (item.media_kind === "video" && item.duration) {
      duration.textContent = fmtDuration(item.duration);
    } else {
      duration.style.display = "none";
    }

    const title = card.querySelector(".card-title");
    title.textContent = titleFor(item);

    const subtitle = card.querySelector(".card-subtitle");
    subtitle.textContent = fmtRelative(item.date);

    const cardBtn = card.querySelector(".card-btn");
    if (cardBtn) {
      cardBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        window.location.href = `/view/${item.message_id}`;
      });
    } else {
      article.addEventListener("click", () => {
        window.location.href = `/view/${item.message_id}`;
      });
    }

    fragment.appendChild(article);

    // Observe this image for lazy loading
    const img = card.querySelector(".lazy-image");

    // Handle image errors - show placeholder
    if (img) {
      img.onerror = () => {
        img.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect width='100' height='100' fill='%230d0d0d'/%3E%3Ctext x='50' y='50' font-family='Arial' font-size='12' fill='%23666' text-anchor='middle' dy='.3em'%3EImage%3C/text%3E%3C/svg%3E";
      };
    }
  }

  elements.grid.appendChild(fragment);
  state.renderedCount = end;
}

// Initialize IntersectionObserver for lazy loading
function initLazyObserver() {
  if (state.lazyObserver) {
    state.lazyObserver.disconnect();
  }

  state.lazyObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        const src = img.dataset.src;
        if (src && !img.src) {
          img.loading = "eager";
          img.decoding = "async";
          img.src = src;
          img.onload = () => {
            img.style.opacity = "1";
            const placeholder = img.previousElementSibling;
            if (placeholder && placeholder.classList.contains("thumb-placeholder")) {
              placeholder.style.display = "none";
            }
          };
          img.onerror = () => {
            img.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect width='100' height='100' fill='%230d0d0d'/%3E%3Ctext x='50' y='50' font-family='Arial' font-size='12' fill='%23666' text-anchor='middle' dy='.3em'%3EImage%3C/text%3E%3C/svg%3E";
            img.style.opacity = "1";
          };
        }
        state.lazyObserver.unobserve(img);
      }
    });
  }, {
    rootMargin: "100px",
    threshold: 0.1
  });
}

// Load more items when button clicked
function loadMore() {
  const hasMoreToRender = state.renderedCount < state.filtered.length;
  const hasMoreOnServer = state.items.length < state.totalItems;

  if (hasMoreToRender) {
    const nextBatch = Math.min(state.renderedCount + state.renderBatchSize, state.filtered.length);
    renderBatch(state.renderedCount, nextBatch);
    updateLoadMoreButton();
  } else if (hasMoreOnServer && !state.isLoading) {
    // Inject skeletons during server fetch for smoother UX
    if (elements.grid) {
      const fragment = document.createDocumentFragment();
      for (let i = 0; i < 6; i++) {
        const dummy = document.createElement("article");
        dummy.className = "card skeleton load-more-skeleton";
        dummy.innerHTML = '<div class="thumb"></div><div class="card-body"><p class="card-title">Loading</p></div>';
        fragment.appendChild(dummy);
      }
      elements.grid.appendChild(fragment);
    }

    // Load more items in batches for better performance over slow connections
    loadMedia(50, state.items.length);
  }
}

// ============================================
// Viewer
// ============================================

function setViewerIndexForItem(item) {
  state.viewerIndex = state.filtered.findIndex(x => x.message_id === item.message_id);
}

function updateViewerNav() {
  if (!elements.viewerPrev || !elements.viewerNext) return;
  const has = Array.isArray(state.filtered) && state.filtered.length > 0 && state.viewerIndex >= 0;
  elements.viewerPrev.disabled = !(has && state.viewerIndex > 0);
  elements.viewerNext.disabled = !(has && state.viewerIndex < state.filtered.length - 1);
}

function openViewer(item, recomputeIndex = true) {
  if (!item) {
    console.error("openViewer: no item provided");
    showToast("Error: No item to display", "error");
    return;
  }

  if (!elements.viewer) {
    console.error("openViewer: viewer element not found");
    showToast("Error: Viewer not found", "error");
    return;
  }

  if (!elements.viewerMedia) {
    console.error("openViewer: viewerMedia element not found");
    showToast("Error: Media container not found", "error");
    return;
  }

  console.log("Opening viewer for:", item.message_id, item.media_kind, "cached:", item.is_cached, "url:", item.url);

  if (recomputeIndex) setViewerIndexForItem(item);
  updateViewerNav();

  // Save scroll position and push URL state — no hashchange, no reload
  _savedScrollY = window.scrollY;
  history.pushState({ viewer: item.message_id }, "", `#view/${item.message_id}`);

  elements.viewerMedia.innerHTML = "";

  const mediaUrl = item.url || `/media/${item.file_name}`;
  const thumbUrl = item.thumb_url || `/media/${item.file_name}`;
  const fallbackUrl = `/api/file/${item.message_id}`;

  if (item.media_kind === "video") {
    const video = document.createElement("video");
    video.poster = thumbUrl;
    video.controls = true;
    video.autoplay = false;
    video.playsInline = true;
    video.preload = "metadata";
    video.muted = false;

    let retryCount = 0;
    const maxRetries = 2;
    const tryUrls = [mediaUrl, fallbackUrl];

    const tryLoadVideo = (urlIndex) => {
      if (urlIndex >= tryUrls.length) {
        elements.viewerMedia.innerHTML = `
          <div class="video-error">
            <p>Failed to load video</p>
            <p class="error-detail">Click download to save the file</p>
            <a href="${fallbackUrl}" class="btn btn-primary" download style="margin-top: 10px;">Download Video</a>
          </div>
        `;
        return;
      }
      video.src = tryUrls[urlIndex];
    };

    video.addEventListener("error", (e) => {
      console.error("Video load error:", e, video.error, "trying next URL");
      retryCount++;
      if (retryCount <= maxRetries) {
        tryLoadVideo(retryCount);
      }
    });

    video.addEventListener("loadedmetadata", () => {
      console.log("Video loaded:", video.videoWidth, "x", video.videoHeight);
    });

    tryLoadVideo(0);
    elements.viewerMedia.appendChild(video);
  } else {
    const img = document.createElement("img");
    img.alt = titleFor(item);

    let retryCount = 0;
    const tryUrls = [mediaUrl, thumbUrl, fallbackUrl];

    const tryLoadImage = (urlIndex) => {
      if (urlIndex >= tryUrls.length) {
        img.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect width='200' height='200' fill='%231a1a1d'/%3E%3Ctext x='100' y='100' font-family='Arial' font-size='14' fill='%23666' text-anchor='middle' dy='.3em'%3EImage not available%3C/text%3E%3C/svg%3E";
        return;
      }
      img.src = tryUrls[urlIndex];
    };

    img.addEventListener("error", () => {
      console.error("Image load error:", img.src);
      retryCount++;
      tryLoadImage(retryCount);
    });

    tryLoadImage(0);
    elements.viewerMedia.appendChild(img);
  }

  // Update info panel
  if (elements.viewerTitle) elements.viewerTitle.textContent = titleFor(item);
  if (elements.viewerDescription) elements.viewerDescription.textContent = item.ai_description || "No description";
  if (elements.viewerCaption) elements.viewerCaption.textContent = item.caption || "No caption";
  if (elements.viewerType) {
    elements.viewerType.textContent = item.media_kind.toUpperCase();
    elements.viewerType.className = 'meta-badge ' + item.media_kind;
  }
  if (elements.viewerSize) elements.viewerSize.textContent = fmtBytes(item.size);
  if (elements.viewerDate) elements.viewerDate.textContent = fmtDate(item.date);
  if (elements.viewerResolution && item.width && item.height) {
    elements.viewerResolution.textContent = `${item.width}x${item.height}`;
    elements.viewerResolution.classList.remove("hidden");
  } else if (elements.viewerResolution) {
    elements.viewerResolution.classList.add("hidden");
  }
  if (elements.viewerDownload) {
    elements.viewerDownload.href = mediaUrl;
  }

  // Show viewer
  elements.viewer.classList.remove("hidden");
  document.body.style.overflow = "hidden";

  console.log("Viewer opened successfully");

  // Render suggested videos
  renderSuggestedVideos(item);
}

function closeViewer(restoreHistory = true) {
  elements.viewer?.classList.add("hidden");
  document.body.style.overflow = "";
  state.viewerIndex = -1;

  // Stop any playing video
  if (elements.viewerMedia) {
    const video = elements.viewerMedia.querySelector("video");
    if (video) {
      video.pause();
      video.src = "";
    }
    elements.viewerMedia.innerHTML = "";
  }

  // Restore URL without hash
  if (restoreHistory) {
    history.pushState("", document.title, window.location.pathname);
  }

  // Restore scroll position so gallery looks exactly as left
  requestAnimationFrame(() => {
    window.scrollTo({ top: _savedScrollY, behavior: "instant" });
  });
}

function navigateViewer(direction) {
  if (state.viewerIndex < 0) return;
  const newIndex = state.viewerIndex + direction;
  if (newIndex >= 0 && newIndex < state.filtered.length) {
    openViewer(state.filtered[newIndex], false);
    state.viewerIndex = newIndex;
    updateViewerNav();
  }
}

function renderSuggestedVideos(currentItem) {
  const grid = elements.suggestedGrid;
  const section = elements.suggestedSection;

  if (!grid || !section) return;

  // Get random suggestions
  const suggested = state.items
    .filter(item => item.message_id !== currentItem.message_id)
    .sort(() => Math.random() - 0.5)
    .slice(0, 15);

  if (suggested.length === 0) {
    section.classList.add("hidden");
    return;
  }

  section.classList.remove("hidden");
  grid.innerHTML = "";

  suggested.forEach(item => {
    const card = document.createElement("div");
    card.className = "suggested-card";
    card.innerHTML = `
      <div class="suggested-thumb">
        <img src="${item.thumb_url || item.url}" alt="${titleFor(item)}" loading="lazy">
        <span class="suggested-duration">${item.media_kind === "video" ? fmtDuration(item.duration) : ""}</span>
      </div>
      <div class="suggested-info">
        <p class="suggested-item-title">${titleFor(item)}</p>
        <p class="suggested-item-meta">${fmtRelative(item.date)}</p>
      </div>
    `;
    card.addEventListener("click", () => {
      const idx = state.items.findIndex(x => x.message_id === item.message_id);
      if (idx >= 0) {
        openViewer(item);
        state.viewerIndex = idx;
        updateViewerNav();
      }
    });
    grid.appendChild(card);
  });
}

async function generateAIForItem(messageId) {
  try {
    const res = await fetch(`/api/media/${messageId}/generate-ai?mode=force`, {
      method: "POST",
      headers: await requestHeaders(),
    });
    const data = await res.json();
    if (data.ai_title && elements.viewerDescription) {
      elements.viewerDescription.textContent = data.ai_description || "No description";
      // Update the item in state
      const item = state.items.find(x => x.message_id === messageId);
      if (item) {
        item.ai_title = data.ai_title;
        item.ai_description = data.ai_description;
      }
    }
  } catch (error) {
    console.error("AI generation failed:", error);
  }
}

// ============================================
// Event Bindings
// ============================================

function bindEvents() {
  // Search
  elements.searchInput?.addEventListener("input", debounce(() => {
    applyFilter();
    updateUI();
  }, 300));

  // Filter tabs
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      applyFilter();
      updateUI();
    });
  });

  // Sort
  elements.sortSelect?.addEventListener("change", () => {
    applyFilter();
    updateUI();
  });

  // Layout
  elements.layoutDenseBtn?.addEventListener("click", () => {
    document.documentElement.removeAttribute("data-density");
    elements.layoutDenseBtn?.classList.add("active");
    elements.layoutComfortBtn?.classList.remove("active");
  });

  elements.layoutComfortBtn?.addEventListener("click", () => {
    document.documentElement.setAttribute("data-density", "comfort");
    elements.layoutComfortBtn?.classList.add("active");
    elements.layoutDenseBtn?.classList.remove("active");
  });

  // Sync
  elements.syncBtn?.addEventListener("click", async () => {
    elements.syncBtn.disabled = true;
    showToast("Syncing all media from Telegram...", "info");
    try {
      const res = await fetch("/api/sync?limit=200&wait_seconds=30", {
        method: "POST",
        headers: await requestHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        showToast(`Synced ${data.total || 0} items!`, "success");
        await loadMedia(50, 0, false);  // Reload initial batch
      } else {
        const errData = await res.json().catch(() => ({}));
        showToast(errData.detail || "Sync failed", "error");
      }
    } catch (error) {
      console.error("Sync error:", error);
      showToast("Sync error", "error");
    }
    elements.syncBtn.disabled = false;
  });

  // AI
  elements.retitleBtn?.addEventListener("click", async () => {
    elements.retitleBtn.disabled = true;
    showToast("Generating AI titles...", "ai");
    try {
      const res = await fetch("/api/ai-titles?batch_size=25&mode=style", {
        method: "POST",
        headers: await requestHeaders(),
      });
      const data = await res.json();
      showToast(`Generated ${data.generated} AI titles!`, "success");
      await loadMedia();
    } catch (error) {
      showToast("AI error", "error");
    }
    elements.retitleBtn.disabled = false;
  });

  // Load more
  elements.loadMoreBtn?.addEventListener("click", () => {
    if (state.renderedCount < state.filtered.length) {
      // Client-side: load more rendered items
      loadMore();
    } else if (!state.isLoading) {
      // Server-side: fetch more items in batches
      loadMedia(50, state.items.length);
    }
  });

  // Auto-load more when scrolling near bottom
  let scrollTimeout = null;
  window.addEventListener("scroll", () => {
    if (scrollTimeout) clearTimeout(scrollTimeout);

    scrollTimeout = setTimeout(() => {
      if (state.isLoading) return;

      // Check if we have more filtered items to render locally OR more items on server
      const hasMoreToRender = state.renderedCount < state.filtered.length;
      const hasMoreOnServer = state.items.length < state.totalItems;

      // If nothing more to do, return early
      if (!hasMoreToRender && !hasMoreOnServer) return;

      const scrollY = window.scrollY;
      const viewportHeight = window.innerHeight;
      const docHeight = document.documentElement.scrollHeight;

      // Trigger when user scrolls to 80% of page for smoother experience
      if (scrollY + viewportHeight >= docHeight * 0.8) {
        if (hasMoreToRender || hasMoreOnServer) {
          // Use loadMore() for both local and server fetching
          // This ensures skeletons are shown and append-only rendering
          loadMore();
        }
      }
    }, 50); // Faster debounce for smoother response
  });

  // Top button
  elements.toTopBtn?.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  // Viewer navigation
  elements.viewerPrev?.addEventListener("click", () => navigateViewer(-1));
  elements.viewerNext?.addEventListener("click", () => navigateViewer(1));
  elements.closeViewer?.addEventListener("click", closeViewer);

  // Copy link
  elements.viewerCopyLink?.addEventListener("click", () => {
    navigator.clipboard.writeText(window.location.href);
    showToast("Link copied!", "success");
  });

  // Click on media side to close
  document.querySelector(".viewer-media-side")?.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closeViewer();
  });

  // Click on backdrop to close
  elements.viewer?.addEventListener("click", (e) => {
    if (e.target === elements.viewer) closeViewer();
  });

  // Keyboard
  document.addEventListener("keydown", (e) => {
    if (elements.viewer?.classList.contains("hidden")) return;

    if (e.key === "Escape") closeViewer();
    if (e.key === "ArrowLeft") navigateViewer(-1);
    if (e.key === "ArrowRight") navigateViewer(1);
  });
}

function debounce(fn, delay) {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn(...args), delay);
  };
}

// ============================================
// Initialize
// ============================================

async function init() {
  console.log("Initializing gallery app...");

  // Fire visitor tracking beacon (non-blocking, best-effort)
  try {
    const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
    fetch("/api/track", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        referrer: document.referrer,
        page: window.location.pathname,
        tg_user_id: tgUser?.id ?? null,
        tg_username: tgUser?.username ?? null,
      }),
    }).catch(() => { }); // Silent failure — never block page load
  } catch (_) { }

  try {
    initElements();
    console.log("Elements initialized:", Object.keys(elements).filter(k => elements[k]).length, "found");

    bindEvents();
    bindChatEvents();
    console.log("Events bound");

    console.log("Fetching context...");
    const context = await fetchContext();
    console.log("Context fetched:", context ? "OK" : "null");

    console.log("Loading media...");
    const cachedItems = context?.cached_items || 0;
    const shouldRefresh = cachedItems === 0;
    console.log("Cached items:", cachedItems, "shouldRefresh:", shouldRefresh);

    // Load initial batch for fast experience (don't load all at once over slow tunnels)
    const initialLimit = 50;
    const mediaResult = await loadMedia(initialLimit, 0, shouldRefresh);
    console.log("Media loaded:", mediaResult ? "OK" : "failed/null");

    console.log("Final state - items:", state.items.length, "filtered:", state.filtered.length);

    // Make sure grid is visible
    if (elements.grid) {
      elements.grid.style.display = "";
    }

    if (window.location.hash) {
      setTimeout(() => {
        const hash = window.location.hash;
        if (hash.startsWith("#view/")) {
          const id = parseInt(hash.replace(/^#view\//, ""), 10);
          const item = state.items.find(x => Number(x.message_id) === id);
          if (item) openViewer(item);
        }
      }, 500);
    }

    // Browser back button: close viewer instead of navigating away
    window.addEventListener("popstate", (e) => {
      const isViewerOpen = elements.viewer && !elements.viewer.classList.contains("hidden");
      if (isViewerOpen) {
        closeViewer(false); // false = don't push state again (already handled by browser)
      }
    });

    showToast("Gallery loaded successfully", "success", 2000);

    // Start auto-sync in background
    startAutoSync();
  } catch (error) {
    console.error("Init error:", error);
    showToast("Failed to initialize: " + error.message, "error", 10000);
  }
}

// ============================================
// Auto Sync (lightweight background polling)
// ============================================

let _autoSyncInterval = null;

async function autoSync() {
  if (state.isLoading) return;
  try {
    // Lightweight check: only read cached data, no heavy Telegram sync
    const res = await fetch("/api/media?limit=50&offset=0", {
      headers: await requestHeaders(),
    });
    if (res.ok) {
      const data = await res.json();
      const serverTotal = data.total || 0;
      const localTotal = state.totalItems || state.items.length;

      let needsRefresh = false;
      let refreshReason = "";

      if (serverTotal > localTotal) {
        needsRefresh = true;
        refreshReason = `${serverTotal - localTotal} new items available`;
      } else {
        // Check if any visible untitled items got titles
        const topServerItems = data.items || [];
        for (const localItem of state.items.slice(0, 50)) {
          const serverItem = topServerItems.find(x => x.message_id === localItem.message_id);
          if (serverItem) {
            const localHasTitle = localItem.ai_title && !localItem.ai_title.includes("Video #") && !localItem.ai_title.includes("Image #");
            const serverHasTitle = serverItem.ai_title && !serverItem.ai_title.includes("Video #") && !serverItem.ai_title.includes("Image #");
            if (!localHasTitle && serverHasTitle) {
              needsRefresh = true;
              refreshReason = "AI Titles Generated";
              break;
            }
          }
        }
      }

      if (needsRefresh) {
        console.log(`Auto-sync triggering refresh: ${refreshReason}`);
        await loadMedia(50, 0, false);
        showToast(refreshReason, "success", 2000);
      }
    }
  } catch (e) {
    console.debug("Auto-sync error:", e);
  }
}

function startAutoSync() {
  // First check after 5 seconds (let page settle)
  setTimeout(autoSync, 5000);

  // Then check every 60 seconds (lightweight, no Telegram calls)
  _autoSyncInterval = setInterval(autoSync, 60000);
  console.log("Auto-sync started (every 60s, lightweight)");
}

// ============================================
// AI Chat Bubble Logic (Draggable + History)
// ============================================

let _chatDrag = { active: false, startX: 0, startY: 0, fabX: 0, fabY: 0, moved: false, isTouch: false };
let _chatHistory = []; // In-memory history — clears on page refresh

function positionChatPanel() {
  const panel = elements.chatPanel;
  const fab = elements.chatFab;
  if (!panel || !fab) return;

  const fabRect = fab.getBoundingClientRect();
  const vw = window.innerWidth, vh = window.innerHeight;

  // On small screens: full width panel above FAB
  if (vw <= 480) {
    panel.style.left = "8px";
    panel.style.right = "8px";
    panel.style.width = "auto";
    panel.style.bottom = (vh - fabRect.top + 12) + "px";
    panel.style.top = "auto";
    return;
  }

  const pw = 360, ph = 500;
  let left = fabRect.left - pw + 56;
  let bottom = vh - fabRect.top + 12;

  if (left < 8) left = 8;
  if (left + pw > vw - 8) left = vw - pw - 8;
  if (bottom + ph > vh - 8) bottom = vh - ph - 8;
  if (bottom < 8) bottom = 8;

  panel.style.right = "auto";
  panel.style.width = pw + "px";
  panel.style.bottom = bottom + "px";
  panel.style.left = left + "px";
}

function toggleChat() {
  const panel = elements.chatPanel;
  const fab = elements.chatFab;
  if (!panel || !fab) return;

  const isOpen = panel.classList.contains("open");
  if (!isOpen) {
    positionChatPanel();
    _restoreChatHistory(); // Restore history after viewer or other navigation
  }
  panel.classList.toggle("open");
  fab.classList.toggle("active");

  if (!isOpen) {
    setTimeout(() => elements.chatInput?.focus(), 300);
  }
}

function initChatDrag() {
  const fab = elements.chatFab;
  if (!fab) return;

  function onStart(e) {
    const t = e.touches ? e.touches[0] : e;
    _chatDrag.active = true;
    _chatDrag.moved = false;
    _chatDrag.isTouch = !!e.touches;
    _chatDrag.startX = t.clientX;
    _chatDrag.startY = t.clientY;
    const rect = fab.getBoundingClientRect();
    _chatDrag.fabX = rect.left;
    _chatDrag.fabY = rect.top;
    fab.style.transition = "none";
    if (e.touches) e.preventDefault(); // prevent scroll on touch
  }

  function onMove(e) {
    if (!_chatDrag.active) return;
    const t = e.touches ? e.touches[0] : e;
    const dx = t.clientX - _chatDrag.startX;
    const dy = t.clientY - _chatDrag.startY;

    if (Math.abs(dx) > 8 || Math.abs(dy) > 8) _chatDrag.moved = true;

    if (!_chatDrag.moved) return; // don't move until threshold

    let newX = _chatDrag.fabX + dx;
    let newY = _chatDrag.fabY + dy;

    const vw = window.innerWidth, vh = window.innerHeight;
    newX = Math.max(0, Math.min(newX, vw - 56));
    newY = Math.max(0, Math.min(newY, vh - 56));

    fab.style.position = "fixed";
    fab.style.left = newX + "px";
    fab.style.top = newY + "px";
    fab.style.right = "auto";
    fab.style.bottom = "auto";
    e.preventDefault();
  }

  function onEnd(e) {
    if (!_chatDrag.active) return;
    _chatDrag.active = false;
    fab.style.transition = "";

    if (!_chatDrag.moved) {
      // It was a tap/click — toggle the chat
      // (needed on mobile since preventDefault on touchstart kills click event)
      if (_chatDrag.isTouch) {
        toggleChat();
      }
      return;
    }

    // Snap to nearest edge (left or right)
    const rect = fab.getBoundingClientRect();
    const vw = window.innerWidth;
    if (rect.left + 28 < vw / 2) {
      fab.style.left = "16px";
      fab.style.right = "auto";
    } else {
      fab.style.left = "auto";
      fab.style.right = "16px";
    }

    fab.style.top = "auto";
    fab.style.bottom = "24px";

    if (elements.chatPanel?.classList.contains("open")) {
      setTimeout(positionChatPanel, 50);
    }
  }

  fab.addEventListener("mousedown", onStart);
  document.addEventListener("mousemove", onMove);
  document.addEventListener("mouseup", onEnd);
  fab.addEventListener("touchstart", onStart, { passive: false });
  document.addEventListener("touchmove", onMove, { passive: false });
  document.addEventListener("touchend", onEnd);

  // Desktop click (not touch)
  fab.addEventListener("click", (e) => {
    if (_chatDrag.isTouch) return; // handled by touchend
    if (_chatDrag.moved) return;
    toggleChat();
  });
}

function _restoreChatHistory() {
  const container = elements.chatMessages;
  if (!container) return;
  // Only restore if panel is empty (avoids duplicating on re-open)
  if (container.children.length > 0) return;
  _chatHistory.forEach(({ text, type }) => {
    const msg = document.createElement("div");
    msg.className = `chat-msg ${type}`;
    msg.textContent = text;
    container.appendChild(msg);
  });
  container.scrollTop = container.scrollHeight;
}

function addChatMessage(text, type = "ai") {
  // Save to in-session history (clears on page refresh)
  if (type === "user" || type === "ai") {
    _chatHistory.push({ text, type });
  }
  const msg = document.createElement("div");
  msg.className = `chat-msg ${type}`;
  msg.textContent = text;
  elements.chatMessages?.appendChild(msg);
  if (elements.chatMessages) elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
  return msg;
}

function addTypingIndicator() {
  const msg = document.createElement("div");
  msg.className = "chat-msg ai";
  msg.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
  elements.chatMessages?.appendChild(msg);
  if (elements.chatMessages) elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
  return msg;
}

async function sendChatMessage() {
  const input = elements.chatInput;
  const sendBtn = elements.chatSendBtn;
  if (!input || !sendBtn) return;

  const message = input.value.trim();
  if (!message) return;

  addChatMessage(message, "user");
  input.value = "";
  sendBtn.disabled = true;

  const typing = addTypingIndicator();

  try {
    // Step 1: Start the AI task — server returns task_id immediately (< 100ms)
    const startRes = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(await requestHeaders()),
      },
      body: JSON.stringify({ message }),
    });

    if (!startRes.ok) {
      throw new Error(`Server error ${startRes.status}`);
    }

    const startData = await startRes.json();

    if (!startData.ok) {
      typing.remove();
      const errMsg = addChatMessage(startData.error || "Something went wrong", "ai");
      errMsg.classList.add("error");
      sendBtn.disabled = false;
      input.focus();
      return;
    }

    // Step 2: Poll /api/chat/result/{task_id} every 2s until done
    const taskId = startData.task_id;
    let attempts = 0;
    const maxAttempts = 30; // 30 * 2s = 60s max wait

    const poll = async () => {
      attempts++;
      if (attempts > maxAttempts) {
        typing.remove();
        const errMsg = addChatMessage("AI took too long to respond. Try again.", "ai");
        errMsg.classList.add("error");
        sendBtn.disabled = false;
        input.focus();
        return;
      }

      try {
        const pollRes = await fetch(`/api/chat/result/${taskId}`, {
          headers: await requestHeaders(),
        });
        const pollData = await pollRes.json();

        if (pollData.status === "pending") {
          // Still processing — poll again after 2s
          setTimeout(poll, 2000);
          return;
        }

        typing.remove();
        if (pollData.ok && pollData.reply) {
          addChatMessage(pollData.reply, "ai");
        } else {
          const errMsg = addChatMessage(pollData.error || "Something went wrong", "ai");
          errMsg.classList.add("error");
        }
      } catch (pollErr) {
        typing.remove();
        const errMsg = addChatMessage("Network error during polling", "ai");
        errMsg.classList.add("error");
      }

      sendBtn.disabled = false;
      input.focus();
    };

    // Start polling after 2s (give server time to generate)
    setTimeout(poll, 2000);

  } catch (err) {
    typing.remove();
    const errMsg = addChatMessage("Network error — couldn't reach AI", "ai");
    errMsg.classList.add("error");
    sendBtn.disabled = false;
    input.focus();
  }
}

function bindChatEvents() {
  initChatDrag();

  elements.chatSendBtn?.addEventListener("click", sendChatMessage);

  elements.chatInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });
}

document.addEventListener("DOMContentLoaded", init);

// Global error handler to prevent white screen
window.onerror = function (msg, url, line, col, error) {
  console.error("Global error:", msg, "at line", line);
  const container = document.getElementById("toastContainer") || document.body;
  const errorDiv = document.createElement("div");
  errorDiv.className = "toast error";
  errorDiv.textContent = "Error: " + msg;
  container.appendChild(errorDiv);
  setTimeout(() => errorDiv.remove(), 10000);
  return false;
};

window.addEventListener("unhandledrejection", (event) => {
  console.error("Unhandled rejection:", event.reason);
  const container = document.getElementById("toastContainer") || document.body;
  const errorDiv = document.createElement("div");
  errorDiv.className = "toast error";
  errorDiv.textContent = "Error: " + (event.reason?.message || event.reason);
  container.appendChild(errorDiv);
  setTimeout(() => errorDiv.remove(), 10000);
});
