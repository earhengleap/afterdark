# Telegram Mini App UI Refresh (Tube-Style) - Design

## Goal
Refresh the Telegram Mini App gallery UI (`telegram-bot-websites/`) into a modern “tube-site” layout: dense thumbnail wall, sticky search/filter controls, and a theater-style viewer with fast browsing. Keep copy neutral (no explicit UI text), while still feeling like an adult vault brand.

## Constraints
- Must work well inside Telegram WebApp (mobile-first, safe-area insets, BackButton integration).
- Must stay lightweight over tunnels (avoid autoplay previews; keep lazy-loading for thumbs).
- No new build tooling (keep plain HTML/CSS/JS; no bundler).

## Information Architecture
- Sticky **top nav**: brand + compact session/connection status + search + primary actions (`Sync`, `Improve Titles`).
- Sticky **filter bar**: media chips (`All`, `Videos`, `Images`), sort, and a `Dense/Comfort` layout toggle.
- **Grid**: mixed aspect ratios (videos 16:9, images 4:5) with overlays: kind, cache state, duration (video), resolution badges (HD/4K when known).

## Viewer
- Desktop/tablet: “theater” layout (media left, info panel right).
- Mobile: full-screen media with a bottom-sheet info panel.
- Navigation: `Prev/Next` buttons + keyboard arrow support + swipe affordances on mobile (optional).

## Data Usage
- Title: `ai_title` (fallback to caption/file).
- Description teaser: `ai_description` (fallback to size/time).
- Badges: `duration`, `width/height`, `is_cached`, `media_kind`.

## Non-Goals
- No explicit pornographic text/graphics in UI.
- No heavy hover previews or preloading full videos.

