// view.js
// Runs ONLY on the dedicated /view/{id} page

document.addEventListener("DOMContentLoaded", async () => {
    // Extract message ID from URL path (e.g. /view/12345)
    const pathParts = window.location.pathname.split("/");
    const messageId = pathParts[pathParts.length - 1];

    if (!messageId || isNaN(messageId)) {
        document.getElementById("mediaWrapper").innerHTML = "<div style='color: var(--danger)'>Invalid Media ID Error</div>";
        return;
    }

    try {
        const res = await fetch(`/api/media/${messageId}`);
        if (!res.ok) {
            document.getElementById("mediaWrapper").innerHTML = `<div style='color: var(--danger)'>Failed to load media (HTTP ${res.status})</div>`;
            return;
        }

        const data = await res.json();
        if (!data.ok || !data.item) {
            document.getElementById("mediaWrapper").innerHTML = `<div style='color: var(--danger)'>Media not found in database</div>`;
            return;
        }

        renderMedia(data.item);

    } catch (e) {
        document.getElementById("mediaWrapper").innerHTML = `<div style='color: var(--danger)'>Network error: ${e.message}</div>`;
    }
});

function renderMedia(item) {
    const wrapper = document.getElementById("mediaWrapper");
    const url = item.url || `/api/file/${item.message_id}`;

    // Decide HTML structure based on video/image
    if (item.media_kind === "video") {
        wrapper.innerHTML = `
      <video controls playsinline autoplay style="width: 100%; height: 100%; max-height: 70vh; outline: none;">
        <source src="${url}" type="video/mp4">
        Your browser does not support the video tag.
      </video>
    `;
    } else {
        wrapper.innerHTML = `
      <img src="${url}" alt="Media Image" style="max-width: 100%; max-height: 70vh; object-fit: contain;">
    `;
    }

    // Populate Meta
    document.getElementById("mediaTitle").textContent = item.ai_title || "Untitled Media";

    const dateObj = new Date(item.date);
    const sizeMB = parseFloat(item.file_size_mb || 0).toFixed(1);
    const resStr = item.width && item.height ? `${item.width}x${item.height} • ` : "";

    document.getElementById("mediaDate").textContent = `Uploaded ${dateObj.toLocaleDateString()} • ${resStr}${sizeMB}MB`;

    // Description / Caption Fallback
    const descEl = document.getElementById("mediaDesc");
    if (item.ai_description) {
        descEl.textContent = item.ai_description;
    } else if (item.caption) {
        descEl.textContent = item.caption;
    } else {
        descEl.textContent = "No description available for this media.";
        descEl.style.fontStyle = "italic";
        descEl.style.opacity = "0.5";
    }

    // Inject generic Download Button
    document.querySelector(".top-actions").innerHTML = `
    <a href="${url}" download class="btn btn-primary" style="text-decoration: none;">Download File</a>
  `;

    // Fetch and Render Suggested Videos
    loadSuggestedVideos(item.message_id);
}

function fmtDuration(seconds) {
    if (!seconds) return "";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
}

async function loadSuggestedVideos(currentId) {
    try {
        const res = await fetch(`/api/media?limit=100`);
        if (!res.ok) return;
        const data = await res.json();
        if (!data.items) return;

        // Filter out the current item, randomize order, pick top 15
        const suggested = data.items
            .filter(x => x.message_id !== currentId)
            .sort(() => Math.random() - 0.5)
            .slice(0, 15);

        if (suggested.length === 0) return;

        const grid = document.getElementById("suggestedGrid");
        const section = document.getElementById("suggestedSection");

        section.classList.remove("hidden");
        grid.innerHTML = "";

        suggested.forEach(item => {
            const card = document.createElement("div");
            card.className = "suggested-card";

            const title = item.ai_title || item.caption || `${item.media_kind} #${item.message_id}`;
            const thumbUrl = item.thumb_url || item.url || `/api/file/${item.message_id}`;
            const duration = item.media_kind === "video" && item.duration ? fmtDuration(item.duration) : "";
            const dateStr = item.date ? new Date(item.date).toLocaleDateString() : "";

            card.innerHTML = `
                <div class="suggested-thumb">
                    <img src="${thumbUrl}" alt="Thumbnail" loading="lazy">
                    <span class="suggested-duration">${duration}</span>
                </div>
                <div>
                    <p class="suggested-item-title">${title}</p>
                    <p class="suggested-item-meta">${dateStr}</p>
                </div>
            `;

            // Navigate to the new item when clicked
            card.addEventListener("click", () => {
                window.location.href = `/view/${item.message_id}`;
            });

            grid.appendChild(card);
        });

    } catch (err) {
        console.error("Failed to load suggested:", err);
    }
}
