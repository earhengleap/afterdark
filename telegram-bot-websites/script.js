const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

const state = {
  items: [],
  filtered: [],
  filter: "all",
  search: "",
  syncAt: null,
  initData: tg ? tg.initData : "",
  context: null,
  syncError: null,
  sessionMode: null,
};

const elements = {
  sessionText: document.getElementById("sessionText"),
  syncBtn: document.getElementById("syncBtn"),
  searchInput: document.getElementById("searchInput"),
  tabs: Array.from(document.querySelectorAll(".tab")),
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

function callHaptic(kind = "light") {
  if (!tg || !tg.HapticFeedback) return;
  try {
    tg.HapticFeedback.impactOccurred(kind);
  } catch (_) {
    // ignore
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
  let status = state.syncAt ? `Synced ${fmtRelative(state.syncAt)}` : "Not synced";
  if (state.sessionMode) {
    status += ` . mode:${state.sessionMode}`;
  }
  elements.countText.textContent = `${state.filtered.length} items`;
  elements.syncText.textContent = status;
}

function applyFilter() {
  const q = state.search.trim().toLowerCase();

  state.filtered = state.items.filter((item) => {
    if (state.filter !== "all" && item.media_kind !== state.filter) return false;
    if (!q) return true;
    const hay = `${item.caption || ""} ${item.file_name || ""}`.toLowerCase();
    return hay.includes(q);
  });

  renderGrid();
}

function thumbHtml(item) {
  if (item.media_kind === "video") {
    return `<video muted preload="metadata" playsinline src="${item.url}"></video>`;
  }
  return `<img loading="lazy" src="${item.url}" alt="${titleFor(item)}">`;
}

function renderGrid() {
  elements.grid.innerHTML = "";

  if (!state.filtered.length) {
    elements.emptyState.classList.remove("hidden");
    updateMetaRow();
    return;
  }

  elements.emptyState.classList.add("hidden");

  state.filtered.forEach((item) => {
    const node = elements.cardTemplate.content.firstElementChild.cloneNode(true);
    const button = node.querySelector(".card-btn");
    const thumb = node.querySelector(".thumb");
    const title = node.querySelector(".card-title");
    const subtitle = node.querySelector(".card-subtitle");

    thumb.insertAdjacentHTML("afterbegin", thumbHtml(item));
    thumb.insertAdjacentHTML("beforeend", `<span class="badge">${item.media_kind.toUpperCase()}</span>`);

    title.textContent = titleFor(item);
    subtitle.textContent = `${fmtBytes(item.size)} . ${fmtRelative(item.date)}`;

    button.addEventListener("click", () => openViewer(item));
    elements.grid.appendChild(node);
  });

  updateMetaRow();
}

function openViewer(item) {
  elements.viewerMedia.innerHTML = "";

  if (item.media_kind === "video") {
    const v = document.createElement("video");
    v.src = item.url;
    v.controls = true;
    v.autoplay = true;
    v.playsInline = true;
    elements.viewerMedia.appendChild(v);
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

function applyApiPayload(data) {
  state.items = Array.isArray(data.items) ? data.items : [];
  state.syncAt = data.synced_at || null;
  state.syncError = data.sync_error || null;
  state.sessionMode = data.session_mode || null;

  renderStats();
  applyFilter();

  if (state.syncError) {
    showSyncError(state.syncError);
  }
}

async function loadMedia(refresh = false) {
  const url = `/api/media?limit=1000${refresh ? "&refresh=true" : ""}`;
  const res = await fetch(url, {
    headers: requestHeaders(),
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Failed to load media");
  }

  const data = await res.json();
  applyApiPayload(data);
}

async function syncNow() {
  elements.syncBtn.disabled = true;
  elements.syncBtn.textContent = "Syncing...";

  try {
    const res = await fetch("/api/sync?limit=1000", {
      method: "POST",
      headers: requestHeaders(),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "Sync failed");
    }

    const data = await res.json();
    applyApiPayload(data);
    callHaptic("light");
  } finally {
    elements.syncBtn.disabled = false;
    elements.syncBtn.textContent = "Sync";
  }
}

function setupMiniAppChrome() {
  if (!tg) return;

  try {
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#111111");
    tg.setBackgroundColor("#0e0e10");
  } catch (_) {
    // ignore
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
    applyFilter();
  });

  elements.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      elements.tabs.forEach((x) => x.classList.remove("active"));
      tab.classList.add("active");
      state.filter = tab.dataset.filter;
      applyFilter();
      callHaptic("light");
    });
  });

  elements.syncBtn.addEventListener("click", async () => {
    try {
      await syncNow();
    } catch (error) {
      console.error(error);
      alert("Sync failed. Check server logs.");
    }
  });

  elements.closeViewer.addEventListener("click", closeViewer);
  elements.viewer.addEventListener("click", (event) => {
    if (event.target === elements.viewer) {
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
