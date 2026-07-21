# Stitch Preservation Contract

## Protected baseline

- Montserrat brand/headings and Source Sans 3 body typography.
- Light page, white cards/header/navigation, blue brand/actions, slate-muted controls.
- Sticky 64px header, centered 712px feed, 24px gaps, 12px rounded bordered cards.
- Mobile edge-to-edge cards and fixed 64px bottom navigation below the `md` breakpoint.
- Existing card anatomy: avatar/title/date/menu, expandable text, optional media, metrics, and three actions.
- Three-card shimmer language for initial and append loading.

Refactors may move state and markup into focused modules, but they preserve DOM order, class behavior, sizes, breakpoints, typography, icon language, and loading placement. Intentional changes require explicit approval and before/after visual review.

## Demo retirement

The fabricated posts, names, counts, generated copy, timer delays, Unsplash images, pravatar avatars, `LearnScroll` branding, `Search Connect`, and Facebook-style navigation labels are prototype content. Replace them only through an approved product/content decision and the API/view-model boundary. Production never silently falls back to plausible demo content.

Use Wikimedia-compatible media with canonical provenance and attribution. Decide whether to self-host fonts; document any remaining external origin in CSP/privacy policy. Provide meaningful image alternatives, named icon controls, active navigation semantics, loading announcements, safe-area handling, and a reduced-motion shimmer alternative.
