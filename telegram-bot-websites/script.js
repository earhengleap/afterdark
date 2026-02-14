const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

const state = {
  items: [],
  filtered: [],
  filter: "all",
  sort: "newest",
  search: "",
  syncAt: null,
  initData: tg ? tg.initData : "",
  context: null,
  syncError: null,
  sessionMode: null,
  visibleCount: 0,
  pageSize: 36,
  thumbObserver: null,
  syncing: false,
};

const elements = {
  sessionText: document.getElementById("sessionText"),
  syncBtn: document.getElementById("syncBtn"),
  toTopBtn: document.getElementById("toTopBtn"),
  loadMoreBtn: document.getElementById("loadMoreBtn"),
  searchInput: document.getElementById("searchInput"),
  tabs: Array.from(document.querySelectorAll(".tab")),
  sortSelect: document.getElementById("sortSelect"),
  countText: document.getElementById("countText"),
  syncText: document.getElementById("syncText"),
  statTotal: document.getElementById("statTotal"),
  statVideos: document.getElementById("statVideos"),
  statImages: document.getElementById("statImages"),
  statSize: document.getElementById("statSize"),
  grid: document.getElementById("grid"),
  emptyState: document.getElementById("emptyState"),
  cardTemplate: document.getElementById("cardTemplate"),
  viewer: document.getElementById("viewer"),
  viewerMedia: document.getElementById("viewerMedia"),
  viewerTitle: document.getElementById("viewerTitle"),
  viewerCaption: document.getElementById("viewerCaption"),
  viewerType: document.getElementById("viewerType"),
  viewerSize: document.getElementById("viewerSize"),
  viewerDate: document.getElementById("viewerDate"),
  viewerDownload: document.getElementById("viewerDownload"),
  closeViewer: document.getElementById("closeViewer"),
};

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
  return `${Math.floor(delta / 86400)}d ago`;
}

function fmtDate(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Unknown";
  return d.toLocaleString();
}

function titleFor(item) {
  const caption = (item.caption || "").trim();
  if (caption) return caption.split("\n")[0];
  return item.file_name || `message-${item.message_id}`;
}

function asTime(iso) {
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
}

function callHaptic(kind = "light") {
  if (!tg || !tg.HapticFeedback) return;
  try {
    tg.HapticFeedback.impactOccurred(kind);
  } catch (_) {
    // no-op
  }
}

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
  elements.sessionText.textContent = message;
}

function showSyncError(errorText) {
  if (!errorText) return;
  setSessionText(errorText);
  if (tg && tg.showAlert) {
    tg.showAlert(errorText);
  }
}

async function fetchContext() {
  const res = await fetch("/api/webapp/context", {
    headers: requestHeaders(),
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Failed to get webapp context");
  }

  state.context = await res.json();

  if (state.context.is_telegram_webapp) {
    const user = state.context.payload && state.context.payload.user ? state.context.payload.user : null;
    const uname = user ? (user.username ? `@${user.username}` : user.first_name || "Telegram user") : "Telegram user";
    const verify = state.context.verified ? "verified" : "not verified";
    setSessionText(`${uname} . ${verify} . Mini App mode`);
  } else {
    setSessionText("Browser mode (outside Telegram Mini App)");
  }
}

function renderStats() {
  const total = state.items.length;
  const videos = state.items.filter((x) => x.media_kind === "video").length;
  const images = total - videos;
  const size = state.items.reduce((sum, x) => sum + (Number(x.size) || 0), 0);

  elements.statTotal.textContent = String(total);
  elements.statVideos.textContent = String(videos);
  elements.statImages.textContent = String(images);
  elements.statSize.textContent = fmtBytes(size);
}

function updateMetaRow() {
  const showing = Math.min(state.visibleCount, state.filtered.length);
  let status = state.syncAt ? `Synced ${fmtRelative(state.syncAt)}` : "Not synced";
  if (state.sessionMode) {
    status += ` . ${state.sessionMode} mode`;
  }
  elements.countText.textContent = `Showing ${showing} of ${state.filtered.length}`;
  elements.syncText.textContent = status;
}

function applySort(items) {
  const list = [...items];
  if (state.sort === "oldest") {
    list.sort((a, b) => asTime(a.date) - asTime(b.date));
  } else if (state.sort === "largest") {
    list.sort((a, b) => (Number(b.size) || 0) - (Number(a.size) || 0));
  } else {
    list.sort((a, b) => asTime(b.date) - asTime(a.date));
  }
  return list;
}

function applyFilter(resetVisible = true) {
  const q = state.search.trim().toLowerCase();
  let items = state.items;

  if (state.filter !== "all") {
    items = items.filter((item) => item.media_kind === state.filter);
  }

  if (q) {
    items = items.filter((item) => {
      const hay = `${item.caption || ""} ${item.file_name || ""}`.toLowerCase();
      return hay.includes(q);
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

function ensureObserver() {
  if (state.thumbObserver) {
    state.thumbObserver.disconnect();
  }
  state.thumbObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
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
      rootMargin: "240px 0px",
      threshold: 0.05,
    },
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

  const finish = () => {
    thumb.classList.add("loaded");
  };
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
    { once: true },
  );

  mediaSlot.appendChild(media);
  if (state.thumbObserver) {
    state.thumbObserver.observe(media);
  }
}

function updateLoadMoreButton() {
  const hasMore = state.visibleCount < state.filtered.length;
  elements.loadMoreBtn.classList.toggle("hidden", !hasMore);
}

function renderGrid() {
  elements.grid.innerHTML = "";

  if (!state.filtered.length) {
    elements.emptyState.classList.remove("hidden");
    updateMetaRow();
    updateLoadMoreButton();
    return;
  }

  elements.emptyState.classList.add("hidden");
  ensureObserver();

  const visibleItems = state.filtered.slice(0, state.visibleCount);
  const fragment = document.createDocumentFragment();

  visibleItems.forEach((item, idx) => {
    const node = elements.cardTemplate.content.firstElementChild.cloneNode(true);
    node.style.setProperty("--delay", `${(idx % 24) * 16}ms`);

    const button = node.querySelector(".card-btn");
    const thumb = node.querySelector(".thumb");
    const mediaSlot = node.querySelector(".media-slot");
    const kindBadge = node.querySelector(".badge-kind");
    const cacheBadge = node.querySelector(".badge-cache");
    const title = node.querySelector(".card-title");
    const subtitle = node.querySelector(".card-subtitle");

    wireThumbMedia(item, thumb, mediaSlot);

    kindBadge.textContent = item.media_kind;
    cacheBadge.textContent = item.is_cached ? "cached" : "stream";
    cacheBadge.classList.add(item.is_cached ? "cached" : "stream");

    title.textContent = titleFor(item);
    subtitle.textContent = `${fmtBytes(item.size)} . ${fmtRelative(item.date)}${item.is_cached ? "" : " . on demand"}`;

    button.addEventListener("click", () => openViewer(item));
    fragment.appendChild(node);
  });

  elements.grid.appendChild(fragment);
  updateMetaRow();
  updateLoadMoreButton();
}

function openViewer(item) {
  elements.viewerMedia.innerHTML = "";

  if (item.media_kind === "video") {
    const video = document.createElement("video");
    video.src = item.url;
    video.controls = true;
    video.autoplay = true;
    video.playsInline = true;
    video.preload = "metadata";
    elements.viewerMedia.appendChild(video);
  } else {
    const img = document.createElement("img");
    img.src = item.url;
    img.alt = titleFor(item);
    elements.viewerMedia.appendChild(img);
  }

  elements.viewerTitle.textContent = titleFor(item);
  elements.viewerCaption.textContent = item.caption || "No caption";
  elements.viewerType.textContent = item.media_kind;
  elements.viewerSize.textContent = fmtBytes(item.size);
  elements.viewerDate.textContent = fmtDate(item.date);
  elements.viewerDownload.href = item.url;
  elements.viewerDownload.setAttribute("download", item.file_name || "media");

  elements.viewer.classList.remove("hidden");
  elements.viewer.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";

  if (tg && tg.BackButton) {
    tg.BackButton.show();
  }
  callHaptic("medium");
}

function closeViewer() {
  elements.viewer.classList.add("hidden");
  elements.viewer.setAttribute("aria-hidden", "true");
  elements.viewerMedia.innerHTML = "";
  document.body.style.overflow = "";

  if (tg && tg.BackButton) {
    tg.BackButton.hide();
  }
}

function normalizeItems(items) {
  return items.map((item) => {
    const isCached = typeof item.is_cached === "boolean" ? item.is_cached : String(item.url || "").startsWith("/media/");
    const thumbUrl = item.thumb_url || (item.media_kind === "image" ? item.url : "/assets/video-placeholder.svg");
    return {
      ...item,
      is_cached: isCached,
      thumb_url: thumbUrl,
    };
  });
}

function applyApiPayload(data, resetVisible = true) {
  state.items = Array.isArray(data.items) ? normalizeItems(data.items) : [];
  state.syncAt = data.synced_at || null;
  state.syncError = data.sync_error || null;
  state.sessionMode = data.session_mode || null;

  renderStats();
  applyFilter(resetVisible);

  if (state.syncError) {
    showSyncError(state.syncError);
  }
}

async function loadMedia(refresh = false) {
  const url = `/api/media?limit=all${refresh ? "&refresh=true" : ""}`;
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

function setSyncButtonLoading(isLoading) {
  state.syncing = isLoading;
  elements.syncBtn.disabled = isLoading;
  elements.syncBtn.textContent = isLoading ? "Syncing..." : "Sync Media";
}

async function syncNow() {
  setSyncButtonLoading(true);
  try {
    const res = await fetch("/api/sync?limit=all", {
      method: "POST",
      headers: requestHeaders(),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "Sync failed");
    }
    const data = await res.json();
    applyApiPayload(data, true);
    callHaptic("light");
  } finally {
    setSyncButtonLoading(false);
  }
}

function loadMore() {
  if (state.visibleCount >= state.filtered.length) return;
  state.visibleCount = Math.min(state.visibleCount + state.pageSize, state.filtered.length);
  renderGrid();
}

function setupMiniAppChrome() {
  if (!tg) return;
  try {
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#12171c");
    tg.setBackgroundColor("#0d1117");
  } catch (_) {
    // no-op
  }

  if (tg.BackButton) {
    tg.BackButton.onClick(() => {
      if (!elements.viewer.classList.contains("hidden")) {
        closeViewer();
      }
    });
  }

  if (tg.MainButton) {
    tg.MainButton.setText("SYNC MEDIA");
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

function bindUI() {
  elements.searchInput.addEventListener("input", (ev) => {
    state.search = ev.target.value;
    applyFilter(true);
  });

  elements.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      elements.tabs.forEach((x) => {
        x.classList.remove("active");
        x.setAttribute("aria-selected", "false");
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      state.filter = tab.dataset.filter;
      applyFilter(true);
      callHaptic("light");
    });
  });

  elements.sortSelect.addEventListener("change", (ev) => {
    state.sort = ev.target.value;
    applyFilter(true);
  });

  elements.syncBtn.addEventListener("click", async () => {
    try {
      await syncNow();
    } catch (error) {
      console.error(error);
      alert("Sync failed. Check server logs.");
    }
  });

  elements.loadMoreBtn.addEventListener("click", () => {
    loadMore();
  });

  elements.toTopBtn.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  window.addEventListener("scroll", () => {
    const nearBottom = window.innerHeight + window.scrollY >= document.body.offsetHeight - 300;
    if (nearBottom && !state.syncing) {
      loadMore();
    }
  });

  elements.closeViewer.addEventListener("click", closeViewer);
  elements.viewer.addEventListener("click", (event) => {
    if (event.target === elements.viewer || event.target.classList.contains("viewer-backdrop")) {
      closeViewer();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !elements.viewer.classList.contains("hidden")) {
      closeViewer();
    }
  });
}

async function bootstrap() {
  bindUI();
  setupMiniAppChrome();

  try {
    await fetchContext();
    await loadMedia(false);
  } catch (error) {
    console.error(error);
    setSessionText("Failed to initialize Mini App");
    elements.emptyState.classList.remove("hidden");
    elements.emptyState.innerHTML = "<p>Failed to load media. Check bot access and server logs.</p>";
  }
}

bootstrap();
