import { useCallback, useEffect, useRef, useState } from "react"
import { ArrowLeft, Heart, History, MessageCircle, Search, Send } from "lucide-react"
import { Badge, type BadgeProps } from "./components/ui/badge"
import { YearRangeFilter } from "./components/YearRangeFilter"

type Topic = { name: string; variant: NonNullable<BadgeProps["variant"]> }
type Post = { id: string; year: number; date: string; headline: string; content: string; likes: number; comments: number; shares?: number; source: string; sourceUrl?: string; topics: Topic[] }

// ── API types ──────────────────────────────────────────────────────────────
type ApiItem = {
  id: string
  profileName: string
  profilePhotoUrl: string
  contentType: string
  contentText: string
  historicalDate: { startYear: number; precision: string; label: string; endYear?: number }
  tags: string[]
  likesCount: number
  commentsCount: number
  sharesCount: number
  sourceUrl?: string
  sourceTitle?: string
}

const VARIANT_MAP: Record<string, NonNullable<BadgeProps["variant"]>> = {
  physics: "science", chemistry: "science", research: "science", elements: "science",
  science: "science", invention: "science", nobel: "science",
  usa: "usa", "civil-war": "usa", abolition: "usa", law: "usa",
  art: "art", painting: "art", milan: "art", florence: "art",
  ancient: "ww2", egypt: "ww2", rome: "ww2", naval: "ww2",
}

function tagToTopic(tag: string): Topic {
  return {
    name: tag.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
    variant: VARIANT_MAP[tag] ?? "science",
  }
}

async function fetchAllPosts(): Promise<ApiItem[]> {
  const items: ApiItem[] = []
  let cursor: string | null = null
  do {
    const url = cursor
      ? `/api/feed?cursor=${encodeURIComponent(cursor)}&limit=50`
      : "/api/feed?limit=50"
    const res = await fetch(url)
    if (!res.ok) break
    const data: { items: ApiItem[]; nextCursor: string | null } = await res.json()
    items.push(...data.items)
    cursor = data.nextCursor
  } while (cursor)
  return items
}

function matchesQuery(item: ApiItem, q: string): boolean {
  const lq = q.toLowerCase()
  return (item.sourceTitle ?? "").toLowerCase().includes(lq)
    || item.contentText.toLowerCase().includes(lq)
    || item.tags.some(t => t.toLowerCase().includes(lq))
    || item.profileName.toLowerCase().includes(lq)
}

function yearBoundsOf(items: ApiItem[]): [number, number] {
  if (!items.length) return [1780, 2026]
  const years = items.map(i => i.historicalDate.startYear)
  const lo = Math.min(...years), hi = Math.max(...years)
  return [lo, lo === hi ? lo + 1 : hi]
}

const format = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}K` : String(n)
function AdminMark() { return <div aria-hidden="true" className="admin-mark"><History className="size-5" /></div> }

function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-line bg-white p-5 shadow-[0_5px_24px_rgba(28,38,63,.05)]">
      <div className="mb-5 flex gap-3"><div className="shimmer size-10 rounded-xl" /><div className="flex-1 space-y-2 pt-1"><div className="shimmer h-3.5 w-28 rounded" /><div className="shimmer h-3 w-20 rounded" /></div></div>
      <div className="space-y-3"><div className="shimmer h-3 w-24 rounded" /><div className="shimmer h-6 w-4/5 rounded" /><div className="shimmer h-4 w-full rounded" /><div className="shimmer h-4 w-11/12 rounded" /></div>
      <div className="mt-6 flex justify-between border-t border-line/60 pt-4"><div className="shimmer h-5 w-24 rounded" /><div className="shimmer h-5 w-32 rounded" /></div>
    </div>
  )
}

function PostCard({ post }: { post: Post }) {
  const [expanded, setExpanded] = useState(false)
  const [liked, setLiked] = useState(false)
  const [popKey, setPopKey] = useState(0)
  const long = post.content.length > 180
  const copy = !expanded && long ? `${post.content.slice(0, 180).trimEnd()}…` : post.content
  const toggleLike = () => { setLiked(l => !l); if (!liked) setPopKey(k => k + 1) }
  return (
    <article className="history-card rounded-2xl border border-line bg-white shadow-[0_5px_24px_rgba(28,38,63,.05)]">
      <div className="p-5 sm:p-6">
        <header className="mb-4 flex items-start justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <AdminMark />
            <div><h2 className="font-brand text-sm font-bold text-ink">Anon Admin</h2><p className="text-xs text-muted">{post.date}</p></div>
          </div>
        </header>
        <div className="mb-3 flex flex-wrap gap-2">{post.topics.map(t => <Badge key={t.name} variant={t.variant}>{t.name}</Badge>)}</div>
        <h3 className="font-brand text-[21px] font-extrabold leading-[1.22] tracking-tight text-ink sm:text-[24px]">{post.headline}</h3>
        <p className="mt-3 text-[16px] leading-6 text-slate-700">
          {copy}
          {long && <button onClick={() => setExpanded(!expanded)} className="ml-1 cursor-pointer font-semibold text-brand underline underline-offset-2 hover:text-brand/80">{expanded ? "See less" : "See more"}</button>}
        </p>
        <p className="mt-5 border-t border-line/60 pt-3 text-xs font-medium text-muted">
          Source: {post.sourceUrl ? <a href={post.sourceUrl} target="_blank" rel="noopener noreferrer" className="cursor-pointer text-brand underline underline-offset-2 hover:text-brand/80">{post.source}</a> : post.source}
        </p>
      </div>
      <div className="flex items-center gap-8 border-t border-line/60 px-5 py-3 text-sm text-muted sm:px-6">
        <button onClick={toggleLike} className={`flex cursor-pointer items-center gap-1.5 transition-colors ${liked ? "text-red-500" : "hover:text-red-400"}`}>
          <Heart key={popKey} className={`size-4 ${liked ? "heart-pop fill-red-500" : ""}`} />{format(post.likes + (liked ? 1 : 0))}
        </button>
        <span className="flex items-center gap-1.5"><MessageCircle className="size-4" />{format(post.comments)}</span>
        {post.shares && <span className="flex items-center gap-1.5"><Send className="size-4" />{post.shares}</span>}
      </div>
    </article>
  )
}

export default function App() {
  const [query, setQuery] = useState("")
  const [submitted, setSubmitted] = useState(false)
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(false)
  const [moreLoading, setMoreLoading] = useState(false)
  const [yearBounds, setYearBounds] = useState<[number, number]>([1780, 2026])
  const [yearRange, setYearRange] = useState<[number, number]>([1780, 2026])
  const [topics, setTopics] = useState<Topic[]>([])

  const sentinel = useRef<HTMLDivElement>(null)
  const page = useRef(0)
  const locked = useRef(false)
  const matchesRef = useRef<ApiItem[]>([])
  const allApiItems = useRef<ApiItem[]>([])

  // Fetch all posts from backend on mount
  useEffect(() => {
    fetchAllPosts().then(items => {
      allApiItems.current = items
      const seen = new Set<string>()
      const unique: Topic[] = []
      for (const item of items) {
        for (const tag of item.tags) {
          if (!seen.has(tag)) { seen.add(tag); unique.push(tagToTopic(tag)) }
        }
      }
      setTopics(unique)
    })
  }, [])

  const load = useCallback((first = false) => {
    if (locked.current) return
    locked.current = true
    first ? setLoading(true) : setMoreLoading(true)
    window.setTimeout(() => {
      const pool = matchesRef.current
      if (!pool.length) { setLoading(false); setMoreLoading(false); locked.current = false; return }
      const batch = Array.from({ length: 3 }, (_, i) => {
        const index = page.current * 3 + i
        const item = pool[index % pool.length]
        return {
          id: `${item.id}-${index}`,
          year: item.historicalDate.startYear,
          date: item.historicalDate.label,
          headline: item.sourceTitle ?? item.profileName,
          content: item.contentText,
          likes: item.likesCount,
          comments: item.commentsCount,
          shares: item.sharesCount || undefined,
          source: item.sourceTitle ?? item.profileName,
          sourceUrl: item.sourceUrl,
          topics: item.tags.map(tagToTopic),
        } satisfies Post
      })
      page.current += 1
      setPosts(first ? batch : old => [...old, ...batch])
      setLoading(false); setMoreLoading(false); locked.current = false
    }, first ? 600 : 800)
  }, [])

  function commitResults(matches: ApiItem[], label: string) {
    matchesRef.current = matches
    const bounds = yearBoundsOf(matches)
    page.current = 0
    locked.current = false
    setQuery(label)
    setSubmitted(true)
    setPosts([])
    setYearBounds(bounds)
    setYearRange(bounds)
    load(true)
  }

  function handleSubmit() {
    const q = query.trim()
    if (!q) return
    commitResults(allApiItems.current.filter(item => matchesQuery(item, q)), q)
  }

  function exploreTopic(tagName: string) {
    const normalized = tagName.toLowerCase().replace(/\s+/g, "-")
    commitResults(
      allApiItems.current.filter(item => item.tags.some(t => t.toLowerCase() === normalized)),
      tagName,
    )
  }

  function exploreAll() {
    commitResults(allApiItems.current, "")
  }

  function handleBack() {
    setSubmitted(false)
    setPosts([])
    setQuery("")
    page.current = 0
    locked.current = false
  }

  // Infinite scroll
  useEffect(() => {
    if (!submitted) return
    const node = sentinel.current
    if (!node) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !loading) load()
    }, { rootMargin: "280px" })
    observer.observe(node)
    return () => observer.disconnect()
  }, [submitted, load, loading])

  const visiblePosts = posts.filter(p => p.year >= yearRange[0] && p.year <= yearRange[1])
  const noResults = submitted && !loading && matchesRef.current.length === 0

  return (
    <>
      {/* ── Sticky header ── */}
      <header className="sticky top-0 z-20 border-b border-line bg-white/95 px-4 backdrop-blur sm:px-6">
        <div className="mx-auto flex h-16 max-w-[760px] items-center justify-between gap-3">
          <div className="flex items-center gap-3 flex-shrink-0">
            <span className="flex size-9 items-center justify-center rounded-xl bg-brand text-white"><History className="size-5" /></span>
            <span className="font-brand text-xl font-black tracking-tight text-ink">LearnScroll</span>
          </div>

          {/* Header search — appears on submit */}
          <form
            onSubmit={e => { e.preventDefault(); handleSubmit() }}
            className="flex flex-1 items-center gap-2 overflow-hidden transition-all duration-400"
            style={{
              maxWidth: submitted ? 360 : 0,
              opacity: submitted ? 1 : 0,
              pointerEvents: submitted ? "auto" : "none",
            }}
          >
            <label className="flex flex-1 items-center gap-2 rounded-full bg-page px-3 py-2">
              <Search className="size-4 flex-shrink-0 text-muted" />
              <input
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Search history…"
                className="w-full border-0 bg-transparent text-sm outline-none"
              />
            </label>
          </form>

          {/* Back button — appears on submit */}
          <button
            onClick={handleBack}
            className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-semibold text-muted transition-all hover:bg-page hover:text-ink"
            style={{
              opacity: submitted ? 1 : 0,
              pointerEvents: submitted ? "auto" : "none",
              transitionDuration: "300ms",
            }}
            title="Back to home"
          >
            <ArrowLeft className="size-3.5" />
            Go
          </button>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[712px] px-3 sm:px-4">

        {/* ── Hero ── */}
        <section
          className="flex flex-col items-center overflow-hidden transition-all duration-500"
          style={{
            maxHeight: submitted ? 0 : 600,
            opacity: submitted ? 0 : 1,
            paddingTop: submitted ? 0 : "5rem",
            paddingBottom: submitted ? 0 : "3rem",
          }}
        >
          <div className="w-full max-w-[560px] flex flex-col gap-5 text-center">
            <div className="flex flex-col gap-2">
              <p className="font-brand text-[11px] font-bold uppercase tracking-[0.12em] text-brand">Daily dispatches from the past</p>
              <p className="text-sm text-muted">A timeline worth scrolling through.</p>
            </div>
            <h1 className="font-brand text-[clamp(32px,6vw,52px)] font-black leading-[1.1] tracking-tight text-ink">
              Curating the<br />human experience.
            </h1>

            {/* Hero search bar */}
            <form
              onSubmit={e => { e.preventDefault(); handleSubmit() }}
              className="flex items-center gap-3 rounded-2xl border border-line bg-white p-3 shadow-[0_5px_24px_rgba(28,38,63,.07)] transition-shadow focus-within:ring-2 focus-within:ring-brand"
            >
              <input
                autoFocus
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="What do you want to learn about today?"
                className="flex-1 border-0 bg-transparent text-base text-ink outline-none placeholder:text-muted"
              />
              <button
                type="submit"
                className="flex-shrink-0 rounded-xl bg-brand px-5 py-2.5 font-brand text-[15px] font-extrabold text-white transition-transform active:scale-95 hover:bg-brand/90"
              >
                GO!
              </button>
            </form>

            {/* Explore chips */}
            {topics.length > 0 && (
              <div className="flex flex-col items-center gap-3 pt-1">
                <p className="text-sm font-medium text-muted">Or explore a topic</p>
                <div className="flex flex-wrap justify-center gap-2">
                  <Badge
                    role="button"
                    tabIndex={0}
                    onClick={exploreAll}
                    onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); exploreAll() } }}
                    className="cursor-pointer border-line bg-white text-ink transition-transform hover:scale-105 hover:border-brand hover:text-brand focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-1"
                  >
                    All
                  </Badge>
                  {topics.map(t => (
                    <Badge
                      key={t.name}
                      variant={t.variant}
                      role="button"
                      tabIndex={0}
                      onClick={() => exploreTopic(t.name)}
                      onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); exploreTopic(t.name) } }}
                      className="cursor-pointer transition-transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-1"
                    >
                      {t.name}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ── Feed ── */}
        {submitted && (
          <div className="flex flex-col gap-4 pb-24 pt-4">
            {noResults ? (
              <p className="py-16 text-center text-sm text-muted">No results for &ldquo;{query}&rdquo; — try another topic.</p>
            ) : (
              <>
                <YearRangeFilter min={yearBounds[0]} max={yearBounds[1]} value={yearRange} onChange={setYearRange} />
                {loading
                  ? Array.from({ length: 3 }, (_, i) => <SkeletonCard key={i} />)
                  : visiblePosts.map(post => <PostCard key={post.id} post={post} />)
                }
                {moreLoading && Array.from({ length: 3 }, (_, i) => <SkeletonCard key={i} />)}
                <div ref={sentinel} className="h-4" />
              </>
            )}
          </div>
        )}
      </main>
    </>
  )
}
