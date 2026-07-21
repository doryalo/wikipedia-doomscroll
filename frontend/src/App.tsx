import { useCallback, useEffect, useRef, useState } from "react"
import { Heart, History, MessageCircle, Search, Send } from "lucide-react"
import { Badge, type BadgeProps } from "./components/ui/badge"
import { YearRangeFilter } from "./components/YearRangeFilter"

type Topic = { name: string; variant: NonNullable<BadgeProps["variant"]> }
type Post = { id: string; year: number; date: string; headline: string; content: string; likes: number; comments: number; shares?: number; source: string; sourceUrl?: string; topics: Topic[] }
type Fact = Omit<Post, "id" | "date" | "likes" | "comments">

const ALL_FACTS: Fact[] = [
  { year: 1969, headline: "650 Million People Stopped Everything To Watch This Moment", content: "At 10:56 p.m. EDT, Neil Armstrong became the first person to ever walk on the Moon — and almost the entire connected world tuned in to watch. It remains one of the largest live television audiences in history, decades before anyone had a phone in their pocket.", source: "Apollo 11 mission archive", sourceUrl: "https://www.nasa.gov/mission/apollo-11/", topics: [{ name: "Science", variant: "science" }, { name: "USA", variant: "usa" }] },
  { year: 1791, headline: "The 45 Words That Changed What You're Allowed To Say", content: "The First Amendment entered the U.S. Constitution, guaranteeing freedom of religion, speech, press, assembly, and petition — in just 45 words. More than two centuries later, those same words are still being fought over in courtrooms today.", source: "U.S. National Archives", sourceUrl: "https://www.archives.gov/founding-docs/bill-of-rights", topics: [{ name: "USA", variant: "usa" }] },
  { year: 1989, headline: "One Reporter's Mistake Brought Down The Berlin Wall", content: "A mixed-up announcement at an evening press conference sent East Germans rushing to the border crossings. Guards, with no real orders, let them through. Within hours a wall that had divided a city for 28 years was powerless to stop the crowds.", source: "German Historical Museum", sourceUrl: "https://www.dhm.de/en/", topics: [{ name: "WW2", variant: "ww2" }] },
  { year: 1903, headline: "12 Seconds That Changed How Humans Move Forever", content: "Near Kitty Hawk, North Carolina, Orville Wright flew just 120 feet in the Wright Flyer — shorter than the wingspan of a modern jumbo jet. The brothers flew four times that day; their longest flight barely broke a minute. It was enough to invent the future.", source: "Smithsonian National Air and Space Museum", sourceUrl: "https://airandspace.si.edu/", topics: [{ name: "Science", variant: "science" }, { name: "USA", variant: "usa" }] },
  { year: 1945, headline: "51 Countries Made A Promise After The World's Deadliest War — Did They Keep It?", content: "Fifty-one countries brought the United Nations Charter into force, creating an organization built to maintain peace and stop history from repeating itself. Nearly 80 years and dozens of conflicts later, the debate over whether it succeeded is still raging.", source: "United Nations archives", sourceUrl: "https://www.un.org/en/about-us/history-of-the-un", topics: [{ name: "WW2", variant: "ww2" }] },
  { year: 1961, headline: "This Man Orbited The Entire Planet Before Most Of The World Knew His Name", content: "Vostok 1 completed a single orbit of Earth in 108 minutes, making Yuri Gagarin the first human in space. His call sign, Kedr — Russian for cedar — was broadcast to mission control before almost anyone outside the USSR had even heard of him.", source: "Roscosmos historical collection", sourceUrl: "https://www.roscosmos.ru/en/", topics: [{ name: "Science", variant: "science" }] },
  { year: 1981, headline: "The Channel That Promised To Kill The Radio Star — And Almost Did", content: "MTV launched in the United States with the words, 'Ladies and gentlemen, rock and roll.' Within a decade it had reshaped how an entire generation discovered music, turning three-minute videos into the most powerful marketing tool the industry had ever seen.", source: "Museum of Pop Culture", sourceUrl: "https://www.mopop.org/", topics: [{ name: "2000s Pop Culture", variant: "popCulture" }] },
  { year: 1911, headline: "She Vanished From The Louvre For Two Years — And Nobody Even Noticed At First", content: "The Mona Lisa was stolen by a former museum employee and stayed missing for more than two years. Ironically, the empty wall drew more visitors than the painting ever had — and by the time it resurfaced, Leonardo da Vinci's portrait had become the most famous painting on Earth.", source: "Louvre Museum archives", sourceUrl: "https://www.louvre.fr/en/", topics: [{ name: "Art", variant: "art" }] },
]

function matchesQuery(fact: Fact, q: string): boolean {
  const lq = q.toLowerCase()
  return fact.headline.toLowerCase().includes(lq)
    || fact.content.toLowerCase().includes(lq)
    || fact.topics.some(t => t.name.toLowerCase().includes(lq))
}

function yearBoundsOf(facts: Fact[]): [number, number] {
  if (!facts.length) return [1780, 2026]
  const years = facts.map(f => f.year)
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

  const sentinel = useRef<HTMLDivElement>(null)
  const page = useRef(0)
  const locked = useRef(false)
  const matchesRef = useRef<Fact[]>([])

  const load = useCallback((first = false) => {
    if (locked.current) return
    locked.current = true
    first ? setLoading(true) : setMoreLoading(true)
    window.setTimeout(() => {
      const pool = matchesRef.current
      if (!pool.length) { setLoading(false); setMoreLoading(false); locked.current = false; return }
      const batch = Array.from({ length: first ? 3 : 3 }, (_, i) => {
        const index = page.current * 3 + i
        const fact = pool[index % pool.length]
        return { ...fact, id: `post-${index}`, date: `${Math.floor(index / 2) + 1} days ago`, likes: 540 + index * 291, comments: 23 + index * 17 }
      })
      page.current += 1
      setPosts(first ? batch : old => [...old, ...batch])
      setLoading(false); setMoreLoading(false); locked.current = false
    }, first ? 600 : 800)
  }, [])

  function handleSubmit() {
    const q = query.trim()
    if (!q) return
    const matches = ALL_FACTS.filter(f => matchesQuery(f, q))
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
