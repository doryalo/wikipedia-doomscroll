import { useCallback, useEffect, useRef, useState } from "react"
import { ArrowLeft, Heart, MessageCircle, Send } from "lucide-react"
import { Badge, type BadgeProps } from "./components/ui/badge"
import { YearRangeFilter } from "./components/YearRangeFilter"
import { AuthModal, type CurrentUser } from "./components/AuthModal"

type Topic = { name: string; variant: NonNullable<BadgeProps["variant"]> }
type Post = { id: string; apiId: string; profileName: string; profilePhotoUrl?: string; year: number; date: string; headline: string; content: string; likes: number; comments: number; shares?: number; source: string; sourceUrl?: string; topics: Topic[] }

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

const ALL_VARIANTS: NonNullable<BadgeProps["variant"]>[] = ["science", "usa", "art", "ww2", "popCulture"]

function hashVariant(tag: string): NonNullable<BadgeProps["variant"]> {
  let h = 0
  for (const c of tag) h = (h * 31 + c.charCodeAt(0)) & 0xffff
  return ALL_VARIANTS[h % ALL_VARIANTS.length]
}

function tagToTopic(tag: string): Topic {
  return {
    name: tag.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
    variant: VARIANT_MAP[tag.toLowerCase()] ?? hashVariant(tag),
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

function yearBoundsOf(items: ApiItem[]): [number, number] {
  if (!items.length) return [1780, 2026]
  const years = items.map(i => i.historicalDate.startYear)
  const lo = Math.min(...years), hi = Math.max(...years)
  return [lo, lo === hi ? lo + 1 : hi]
}

const format = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}K` : String(n)

const AVATAR_COLORS = ["bg-blue-400", "bg-emerald-400", "bg-violet-400", "bg-amber-400", "bg-rose-400"]
function Avatar({ name, photoUrl }: { name: string; photoUrl?: string }) {
  if (photoUrl) return <img src={photoUrl} alt={name} className="size-10 rounded-xl object-cover object-top flex-shrink-0" />
  let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) & 0xffff
  return <div className={`flex size-10 flex-shrink-0 items-center justify-center rounded-xl ${AVATAR_COLORS[h % AVATAR_COLORS.length]} font-brand text-sm font-black text-white`}>{name[0]}</div>
}

function SkeletonCard() {
  return (
    <div className="rounded-2xl border border-line bg-white p-5 shadow-[0_5px_24px_rgba(28,38,63,.05)]">
      <div className="mb-5 flex gap-3"><div className="shimmer size-10 rounded-xl" /><div className="flex-1 space-y-2 pt-1"><div className="shimmer h-3.5 w-28 rounded" /><div className="shimmer h-3 w-20 rounded" /></div></div>
      <div className="space-y-3"><div className="shimmer h-3 w-24 rounded" /><div className="shimmer h-6 w-4/5 rounded" /><div className="shimmer h-4 w-full rounded" /><div className="shimmer h-4 w-11/12 rounded" /></div>
      <div className="mt-6 flex justify-between border-t border-line/60 pt-4"><div className="shimmer h-5 w-24 rounded" /><div className="shimmer h-5 w-32 rounded" /></div>
    </div>
  )
}

type Liker = { profileId: string; username: string }

function PostCard({ post, currentUser, onAuthRequired }: { post: Post; currentUser: CurrentUser | null; onAuthRequired: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const [liked, setLiked] = useState(false)
  const [popKey, setPopKey] = useState(0)
  const [commentCount, setCommentCount] = useState(post.comments)
  const [showComments, setShowComments] = useState(false)
  const [commentText, setCommentText] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [likers, setLikers] = useState<Liker[] | null>(null)
  const [showLikers, setShowLikers] = useState(false)
  const likerTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const long = post.content.length > 180
  const copy = !expanded && long ? `${post.content.slice(0, 180).trimEnd()}…` : post.content

  const toggleLike = async () => {
    if (!currentUser) { onAuthRequired(); return }
    const nowLiked = !liked
    setLiked(nowLiked)
    if (nowLiked) {
      setPopKey(k => k + 1)
      setLikers(null) // invalidate cache so next hover re-fetches
      await fetch(`/api/posts/${post.apiId}/likes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profileId: currentUser.id }),
      })
    }
  }

  const submitComment = async () => {
    if (!currentUser) { onAuthRequired(); return }
    const text = commentText.trim()
    if (!text || submitting) return
    setSubmitting(true)
    const res = await fetch(`/api/posts/${post.apiId}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profileId: currentUser.id, content: text }),
    })
    if (res.ok) {
      setCommentText("")
      setCommentCount(c => c + 1)
    }
    setSubmitting(false)
  }

  const handleLikeMouseEnter = () => {
    likerTimer.current = setTimeout(async () => {
      if (likers === null) {
        const res = await fetch(`/api/posts/${post.apiId}/likes`)
        if (res.ok) setLikers(await res.json())
      }
      setShowLikers(true)
    }, 300)
  }

  const handleLikeMouseLeave = () => {
    if (likerTimer.current) clearTimeout(likerTimer.current)
    setShowLikers(false)
  }

  return (
    <div className="post-slide">
    <article className="history-card rounded-2xl border border-line bg-white shadow-[0_5px_24px_rgba(28,38,63,.05)]">
      <div className="p-5 sm:p-6">
        <header className="mb-4 flex items-start justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <Avatar name={post.profileName} photoUrl={post.profilePhotoUrl} />
            <div><h2 className="font-brand text-sm font-bold text-ink">{post.profileName}</h2><p className="text-xs text-muted">{post.date}</p></div>
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
        <div className="relative" onMouseEnter={handleLikeMouseEnter} onMouseLeave={handleLikeMouseLeave}>
          <button onClick={toggleLike} className={`flex cursor-pointer items-center gap-1.5 transition-colors ${liked ? "text-red-500" : "hover:text-red-400"}`}>
            <Heart key={popKey} className={`size-4 ${liked ? "heart-pop fill-red-500" : ""}`} />{format(post.likes + (liked ? 1 : 0))}
          </button>
          {showLikers && (
            <div className="absolute bottom-full left-0 mb-2 min-w-[120px] rounded-xl border border-line bg-white px-3 py-2 shadow-[0_8px_24px_rgba(28,38,63,.12)] text-xs text-ink z-10">
              {likers === null
                ? <span className="text-muted">Loading…</span>
                : likers.length === 0
                  ? <span className="text-muted">No likes yet</span>
                  : likers.map(l => <div key={l.profileId} className="py-0.5 font-medium">@{l.username}</div>)
              }
            </div>
          )}
        </div>
        <button onClick={() => { if (!currentUser) { onAuthRequired(); return } setShowComments(c => !c) }} className={`flex cursor-pointer items-center gap-1.5 transition-colors ${showComments ? "text-brand" : "hover:text-brand"}`}>
          <MessageCircle className="size-4" />{format(commentCount)}
        </button>
        {post.shares && <span className="flex items-center gap-1.5"><Send className="size-4" />{post.shares}</span>}
      </div>
      {showComments && (
        <div className="border-t border-line/60 px-5 pb-4 pt-3 sm:px-6">
          <div className="flex gap-2">
            <input
              value={commentText}
              onChange={e => setCommentText(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitComment() } }}
              placeholder="Add a comment…"
              className="flex-1 rounded-lg border border-line bg-page px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus:border-brand focus:ring-1 focus:ring-brand"
            />
            <button
              onClick={submitComment}
              disabled={!commentText.trim() || submitting}
              className="flex-shrink-0 rounded-lg bg-brand px-3 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-40 hover:bg-brand/90"
            >
              {submitting ? "…" : "Post"}
            </button>
          </div>
        </div>
      )}
    </article>
    </div>
  )
}

export default function App() {
  const [submitted, setSubmitted] = useState(false)
  const [posts, setPosts] = useState<Post[]>([])
  const [loading, setLoading] = useState(false)
  const [moreLoading, setMoreLoading] = useState(false)
  const [dataYearBounds, setDataYearBounds] = useState<[number, number]>([1780, 2026])
  const [heroYearRange, setHeroYearRange] = useState<[number, number]>([1780, 2026])
  const [yearBounds, setYearBounds] = useState<[number, number]>([1780, 2026])
  const [yearRange, setYearRange] = useState<[number, number]>([1780, 2026])
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [authModal, setAuthModal] = useState<"login" | "signup" | null>(null)
  const [streak, setStreak] = useState(0)
  const [onThisDay, setOnThisDay] = useState<ApiItem | null>(null)

  const sentinel = useRef<HTMLDivElement>(null)
  const page = useRef(0)
  const locked = useRef(false)
  const matchesRef = useRef<ApiItem[]>([])
  const allApiItems = useRef<ApiItem[]>([])

  // Streak — update on mount
  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10)
    const yesterday = new Date(Date.now() - 864e5).toISOString().slice(0, 10)
    const stored = JSON.parse(localStorage.getItem("ls_streak") ?? '{"date":"","count":0}') as { date: string; count: number }
    const count = stored.date === today ? stored.count : stored.date === yesterday ? stored.count + 1 : 1
    if (stored.date !== today) localStorage.setItem("ls_streak", JSON.stringify({ date: today, count }))
    setStreak(count)
  }, [])

  // Fetch all posts from backend on mount
  useEffect(() => {
    fetchAllPosts().then(items => {
      allApiItems.current = items
      const bounds = yearBoundsOf(items)
      setDataYearBounds(bounds)
      setHeroYearRange(bounds)
      // Pick "On This Day" post deterministically by day-of-year
      if (items.length) {
        const doy = Math.floor((Date.now() - new Date(new Date().getFullYear(), 0, 0).getTime()) / 864e5)
        setOnThisDay(items[doy % items.length])
      }
    })
  }, [])

  const load = useCallback((first = false) => {
    if (locked.current) return
    const pool = matchesRef.current
    const start = page.current * 3
    if (start >= pool.length) return
    locked.current = true
    first ? setLoading(true) : setMoreLoading(true)
    window.setTimeout(() => {
      const batch = pool.slice(start, start + 3).map(item => ({
        id: item.id,
        apiId: item.id,
        profileName: item.profileName,
        profilePhotoUrl: item.profilePhotoUrl || undefined,
        year: item.historicalDate.startYear,
        date: item.historicalDate.label,
        headline: item.sourceTitle ?? item.profileName,
        content: item.contentText,
        likes: Math.floor(Math.random() * 9800) + 200,
        comments: Math.floor(Math.random() * 200) + 5,
        shares: item.sharesCount || undefined,
        source: item.sourceTitle ?? item.profileName,
        sourceUrl: item.sourceUrl,
        topics: item.tags.slice(0, 2).map(tagToTopic),
      } satisfies Post))
      page.current += 1
      setPosts(first ? batch : old => [...old, ...batch])
      setLoading(false); setMoreLoading(false); locked.current = false
    }, first ? 600 : 800)
  }, [])

  function exploreYears([lo, hi]: [number, number]) {
    const matches = allApiItems.current
      .filter(item => { const y = item.historicalDate.startYear; return y >= lo && y <= hi })
      .sort((a, b) => a.historicalDate.startYear - b.historicalDate.startYear)
    matchesRef.current = matches
    const bounds = yearBoundsOf(matches)
    page.current = 0
    locked.current = false
    setSubmitted(true)
    setPosts([])
    setYearBounds(bounds)
    setYearRange(bounds)
    load(true)
  }

  function handleBack() {
    setSubmitted(false)
    setPosts([])
    page.current = 0
    locked.current = false
    setHeroYearRange(dataYearBounds)
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
      {authModal && (
        <AuthModal
          initialTab={authModal}
          onSuccess={user => { setCurrentUser(user); setAuthModal(null) }}
          onClose={() => setAuthModal(null)}
        />
      )}

      {/* ── Sticky header ── */}
      <header className="sticky top-0 z-20 border-b border-line bg-white/95 px-4 backdrop-blur sm:px-6">
        <div className="mx-auto flex h-16 max-w-[760px] items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Back arrow — appears on submit */}
            <button
              onClick={handleBack}
              className="rounded-lg p-1.5 text-muted transition-all hover:bg-page hover:text-ink"
              style={{
                opacity: submitted ? 1 : 0,
                pointerEvents: submitted ? "auto" : "none",
                transitionDuration: "300ms",
                width: submitted ? undefined : 0,
                marginRight: submitted ? undefined : 0,
                overflow: "hidden",
              }}
              title="Back to home"
            >
              <ArrowLeft className="size-4" />
            </button>
            <span className="font-brand text-xl font-black tracking-tight text-ink">LearnScroll</span>
          </div>

          {/* Auth / user controls */}
          <div className="flex flex-shrink-0 items-center gap-2">
            {currentUser && streak > 0 && (
              <span className="flex items-center gap-1 rounded-full bg-orange-50 px-2.5 py-1 text-xs font-bold text-orange-500">
                🔥 {streak}
              </span>
            )}
            {currentUser ? (
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-muted">@{currentUser.username}</span>
                <button
                  onClick={() => setCurrentUser(null)}
                  className="rounded-lg px-2 py-1.5 text-xs font-semibold text-muted transition-colors hover:bg-page hover:text-ink"
                >
                  Log out
                </button>
              </div>
            ) : (
              <>
                <button
                  onClick={() => setAuthModal("login")}
                  className="rounded-lg px-3 py-1.5 text-xs font-semibold text-muted transition-colors hover:bg-page hover:text-ink"
                >
                  Log in
                </button>
                <button
                  onClick={() => setAuthModal("signup")}
                  className="rounded-lg bg-brand px-3 py-1.5 text-xs font-bold text-white transition-opacity hover:bg-brand/90"
                >
                  Sign up
                </button>
              </>
            )}

          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[712px] px-3 sm:px-4">

        {/* ── Hero ── */}
        <section
          className="transition-[grid-template-rows,opacity] duration-500"
          style={{
            display: "grid",
            gridTemplateRows: submitted ? "0fr" : "1fr",
            opacity: submitted ? 0 : 1,
          }}
        >
          <div className="overflow-hidden">
          <div
            className="flex flex-col items-center"
            style={{ paddingTop: "5rem", paddingBottom: "3rem" }}
          >
          <div className="w-full max-w-[560px] flex flex-col gap-6 text-center">
            <div className="flex flex-col gap-2">
              <p className="font-brand text-[11px] font-bold uppercase tracking-[0.12em] text-brand">Daily dispatches from the past</p>
              <p className="text-sm text-muted">A timeline worth scrolling through.</p>
            </div>
            <h1 className="font-brand text-[clamp(32px,6vw,52px)] font-black leading-[1.1] tracking-tight text-ink">
              Curating the<br />human experience.
            </h1>

            {/* On This Day card */}
            {onThisDay && (
              <button
                onClick={() => exploreYears([onThisDay.historicalDate.startYear, onThisDay.historicalDate.startYear])}
                className="w-full rounded-2xl border border-amber-200 bg-amber-50 p-4 text-left transition-all hover:border-amber-300 hover:shadow-md"
              >
                <div className="mb-2 flex items-center gap-2">
                  <span className="rounded-full bg-amber-400 px-2.5 py-0.5 text-[10px] font-black uppercase tracking-widest text-white">On This Day</span>
                  <span className="text-xs font-semibold text-amber-700">{onThisDay.historicalDate.label}</span>
                </div>
                <p className="font-brand text-sm font-extrabold leading-snug text-ink line-clamp-2">
                  {onThisDay.sourceTitle ?? onThisDay.profileName}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-amber-800 line-clamp-2">{onThisDay.contentText}</p>
              </button>
            )}

            {/* Year range slider */}
            <YearRangeFilter
              min={dataYearBounds[0]}
              max={dataYearBounds[1]}
              value={heroYearRange}
              onChange={setHeroYearRange}
            />

            <button
              onClick={() => exploreYears(heroYearRange)}
              className="w-full rounded-xl bg-brand py-3 font-brand text-[15px] font-extrabold text-white transition-transform active:scale-95 hover:bg-brand/90"
            >
              Explore
            </button>
          </div>
          </div>
          </div>
        </section>

        {/* ── Feed ── */}
        {submitted && (
          <div className="flex flex-col gap-4 pb-24 pt-4">
            {noResults ? (
              <p className="py-16 text-center text-sm text-muted">No posts found in that year range — try widening it.</p>
            ) : (
              <>
                <YearRangeFilter min={yearBounds[0]} max={yearBounds[1]} value={yearRange} onChange={setYearRange} />
                {loading
                  ? Array.from({ length: 3 }, (_, i) => <SkeletonCard key={i} />)
                  : visiblePosts.map(post => <PostCard key={post.id} post={post} currentUser={currentUser} onAuthRequired={() => setAuthModal("login")} />)
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
