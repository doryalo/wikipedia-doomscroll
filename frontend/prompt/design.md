# Feed Design Prompt

Build a Facebook-style infinite-scroll feed. Single page, no routing needed.

---

## Post Card

Each post contains:

| Field | Type | Notes |
|---|---|---|
| `title` | string | bold, 1 line max, truncate overflow |
| `content` | string | body text, 3 lines max with "see more" expand |
| `date` | string | relative (e.g. "2 hours ago") |
| `likes` | number | formatted count (e.g. 1.2k) |
| `comments` | number | formatted count |

Visual layout (top → bottom):
```
┌─────────────────────────────────┐
│ [Avatar]  Title          Date   │
│           Content text…         │
│           see more              │
│ ──────────────────────────────  │
│ 👍 1.2k likes    💬 34 comments │
└─────────────────────────────────┘
```

---

## Feed

- Vertical list of Post Cards with consistent gap between cards
- Cards have subtle border or shadow to separate from background
- Constrained max-width (e.g. 680px), centered on page

---

## Infinite Scroll

- Load the first batch on mount (e.g. 10 posts)
- Detect when user scrolls near the bottom (IntersectionObserver on a sentinel element)
- Append next batch on trigger; no "load more" button
- Show skeleton cards at the bottom while loading; replace with real posts on resolve

---

## Skeleton / Shimmer Effect

Skeleton card matches real card dimensions exactly — same height, same padding.

Placeholder elements:
- Avatar circle: fixed size, shimmer
- Title bar: ~60% width, shimmer
- Content lines: 3 lines at 100% / 90% / 70%, shimmer
- Date bar: ~20% width, shimmer
- Footer bar: ~40% width, shimmer

Shimmer animation: a gradient sweep left-to-right, ~1.5s loop.

Show 3 skeleton cards while loading (top of list on first load, bottom on pagination).

---

## States

| State | UI |
|---|---|
| Initial load | 3 skeleton cards fill the viewport |
| Loading more | 3 skeleton cards appended below existing posts |
| Empty feed | Centered message: "No posts yet." |
| Error | Inline banner: "Failed to load posts. Retry." with a retry button |

---

## Data Shape

```ts
interface Post {
  id: string
  title: string
  content: string
  date: string       // ISO or relative string
  likes: number
  comments: number
}
```

Paginated response:

```ts
interface FeedPage {
  posts: Post[]
  nextCursor: string | null  // null = no more pages
}
```

---

## Behavior Notes

- No authentication, no user actions (likes/comments are display-only)
- `nextCursor === null` → stop observing, no more requests
- Debounce or guard against double-firing the intersection callback
- Relative dates recalculate on mount; no live refresh needed
