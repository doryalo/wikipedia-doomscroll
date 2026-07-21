# Changelog

All notable changes to this project will be documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- Interactive like button on post cards: toggle state, optimistic count increment, red fill + pop keyframe animation on click.
- Clickable source citation on each post card (opens the original source URL in a new tab).

### Changed
- Post card content rewritten in clickbait/ragebait style to improve engagement signal; "Historical record" and "On this day · {era}" chrome removed. Cards now lead directly with topic badges, headline, body, and source link.
- Like/comment/share stat spacing widened for legibility.
- See more / See less visually marked as clickable (underline + pointer cursor).

### Removed
- Post-menu ellipsis (⋯) button removed (no backend action to attach to yet).
- `era` field removed from the Post type; `BookOpen` and `Ellipsis` Lucide icons removed as unused.

---

## [0.1.0] — 2026-07-21 — Bootstrap

### Added
- FastAPI backend skeleton with `/live` and `/ready` health endpoints and SQLite readiness check.
- Full documentation tree (Diataxis structure, ADRs, backend and frontend doc layers, agent task boards).
- Frontend feed shell: infinite-scroll feed with IntersectionObserver, skeleton shimmer cards, expand/collapse body, timer-simulated pagination, and hardcoded fixture posts.
- `Post` TypeScript type and JSON Schema for the LearnScroll feed.
- Project AGENTS.md with non-negotiable Wikimedia-API-only constraint and Stitch AI frontend preservation rule.
