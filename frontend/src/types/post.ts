/**
 * Discriminated union for what media a post contains.
 * Renderer uses this to decide which player/layout to show.
 */
export type ContentType = "text" | "image" | "video" | "reel";

/**
 * Core post definition for the LearnScroll feed.
 *
 * Intentionally flat — profile and comment objects are separate schemas
 * to be added later. Only IDs and URLs live here as references.
 *
 * Dates are strings so they survive JSON serialization without conversion.
 */
export type HistoricalDatePrecision =
  | "year"
  | "month"
  | "day"
  | "range"
  | "circa";

/**
 * Represents when an event happened in history.
 *
 * Years use astronomical numbering: 1 BCE is `0`, 2 BCE is `-1`.
 * `label` is the reader-friendly form, for example "15 March 44 BCE"
 * or "c. 1200–1150 BCE".
 */
export interface HistoricalDate {
  startYear: number;
  endYear?: number;
  precision: HistoricalDatePrecision;
  label: string;
}

export interface Post {
  // ── Identity ────────────────────────────────────────────────────────────────
  id: string;          // UUID
  profileId: string;   // FK → Profile.id (future)

  // ── Profile snapshot ────────────────────────────────────────────────────────
  // Denormalized for feed performance — avoid extra profile fetch per card.
  profileName: string;
  profilePhotoUrl: string;

  // ── Content ─────────────────────────────────────────────────────────────────
  contentType: ContentType;
  contentText?: string;      // Caption or article excerpt
  contentImageUrl?: string;  // Static image (contentType === "image")
  contentVideoUrl?: string;  // Video/reel src  (contentType === "video" | "reel")
  thumbnailUrl?: string;     // Poster frame for video before play

  // ── Learning metadata ────────────────────────────────────────────────────────
  /**
   * When the event happened in history — NOT the upload time.
   * Supports approximate dates, ranges, and BCE years.
   */
  historicalDate: HistoricalDate;
  /**
   * When this post was uploaded/created.
   * Used for feed ordering and freshness.
   */
  createdAt: string;

  tags: string[];        // Topic tags, e.g. ["astronomy", "cold war"]
  sourceUrl?: string;    // Citation link (Wikipedia, archive.org, etc.)
  sourceTitle?: string;  // Human-readable citation title

  // ── Social counts ────────────────────────────────────────────────────────────
  likesCount: number;
  commentsCount: number;
  sharesCount?: number;

  // Modal paths are derived by the UI from `id`, e.g. `/posts/${id}/comments`.
}

// ── Future extension points (schemas to add) ─────────────────────────────────
// Profile  { id, name, profilePhotoUrl, bio?, followersCount? }
// Comment  { id, postId, profileId, content, createdAt, likesCount }
// Like     { id, postId, profileId, createdAt }
