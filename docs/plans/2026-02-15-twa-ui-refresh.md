# Telegram Mini App “Tube-Style” UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Modernize the TWA gallery frontend into a dense, tube-style grid with sticky controls and a theater viewer, while keeping performance strong over tunnels.

**Architecture:** Plain HTML/CSS/JS (no build step). UI is driven by the existing `/api/media*` payload and progressively enhanced (lazy thumbs, paging, live updates).

**Tech Stack:** Static web (HTML/CSS/JS) served by FastAPI in `telegram-bot-websites/server.py`.

---

### Task 1: Restructure Header + Controls

**Files:**
- Modify: `telegram-bot-websites/index.html`

**Step 1: Implement updated layout**
- Replace the large hero header + separate toolbar with:
  - Sticky top nav: brand, session status, search, action buttons
  - Sticky filter row: chips, sort, layout toggle

**Step 2: Manual check**
- Run: `python telegram-bot-websites/server.py`
- Open: `http://127.0.0.1:5000/`
- Expected: header remains visible while scrolling; search still focuses/filters.

**Step 3: Commit**
- Run: `git add telegram-bot-websites/index.html`
- Run: `git commit -m "feat: redesign TWA header and controls"`

---

### Task 2: Tube-Style Grid + Badges + Mobile Bottom Sheet

**Files:**
- Modify: `telegram-bot-websites/style.css`

**Step 1: Implement CSS changes**
- Grid: support mixed aspect ratios (video 16:9, image 4:5).
- Card overlays: duration badge, resolution badge, play icon treatment.
- Viewer: theater on desktop; bottom-sheet info on mobile.
- Add `prefers-reduced-motion` guard for animations.

**Step 2: Manual check**
- Resize viewport (mobile/desktop).
- Expected: grid remains dense; viewer info becomes a bottom sheet on mobile.

**Step 3: Commit**
- Run: `git add telegram-bot-websites/style.css`
- Run: `git commit -m "feat: tube-style grid and viewer layout"`

---

### Task 3: Rendering Logic (Duration/Badges/Layout Toggle/Prev-Next)

**Files:**
- Modify: `telegram-bot-websites/script.js`

**Step 1: Add UI state**
- Persist layout (`dense|comfort`) to `localStorage`.
- Add viewer navigation state (current index in `state.filtered`).

**Step 2: Implement rendering updates**
- Subtitle uses `ai_description` teaser when present.
- Add duration formatter for video (mm:ss).
- Add resolution badges based on width/height (HD/4K).
- Add `Prev/Next` buttons and keyboard arrows in viewer.

**Step 3: Manual check**
- Click multiple items; use Prev/Next; confirm viewer updates without closing.
- Expected: no crashes; copy link/embed still works; BackButton closes viewer.

**Step 4: Commit**
- Run: `git add telegram-bot-websites/script.js`
- Run: `git commit -m "feat: enhance TWA rendering and viewer navigation"`

---

### Task 4: Verify + Smoke Test

**Files:**
- Test: `tests/` (no new tests required; run existing suite)

**Step 1: Run tests**
- Run: `python -m unittest discover -s tests`
- Expected: `OK`

**Step 2: Basic UI smoke**
- Run: `python telegram-bot-websites/server.py`
- Expected: home loads, sync works, paging works, viewer works on mobile + desktop.

**Step 3: Commit docs**
- Run: `git add docs/plans/2026-02-15-twa-ui-refresh*.md`
- Run: `git commit -m "docs: add TWA UI refresh design and plan"`

