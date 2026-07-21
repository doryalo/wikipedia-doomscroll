import { useRef, useState } from "react"

const BAR_COUNT = 44
const EDGE_GRAY = [148, 156, 168] as const
const PEAK_BLACK = [17, 24, 33] as const
const lerpMono = (t: number) => {
  const [r1, g1, b1] = EDGE_GRAY, [r2, g2, b2] = PEAK_BLACK
  return `rgb(${r1 + (r2 - r1) * t}, ${g1 + (g2 - g1) * t}, ${b1 + (b2 - b1) * t})`
}

type Props = { min: number; max: number; value: [number, number]; onChange: (v: [number, number]) => void }

export function YearRangeFilter({ min, max, value, onChange }: Props) {
  const [front, setFront] = useState<"lo" | "hi">("hi")
  const containerRef = useRef<HTMLDivElement>(null)

  const pct = (v: number) => ((v - min) / (max - min)) * 100

  const handleLo = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Math.min(Number(e.target.value), value[1])
    onChange([v, value[1]])
  }
  const handleHi = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Math.max(Number(e.target.value), value[0])
    onChange([value[0], v])
  }

  const bars = Array.from({ length: BAR_COUNT }, (_, i) => {
    const barYear = min + (i / (BAR_COUNT - 1)) * (max - min)
    const active = barYear >= value[0] && barYear <= value[1]
    if (!active) return { active: false, height: 35, color: "#c8d0da", opacity: 0.5, glow: "none" }
    const mid = (value[0] + value[1]) / 2
    const half = Math.max((value[1] - value[0]) / 2, 1)
    const t = Math.max(0, 1 - Math.abs(barYear - mid) / half)
    const tEased = t * t * (3 - 2 * t) // smoothstep for nicer falloff
    const height = 38 + tEased * 62
    const color = lerpMono(tEased)
    const glowAlpha = 0.08 + tEased * 0.12
    const glow = `0 0 ${3 + tEased * 5}px rgba(17,24,33,${glowAlpha})`
    return { active: true, height, color, opacity: 1, glow }
  })

  const gloLo = pct(value[0])
  const gloHi = pct(value[1])

  return (
    <div className="rounded-2xl border border-line bg-white px-5 py-4 shadow-[0_5px_24px_rgba(28,38,63,.05)] sm:px-6">
      <p className="mb-3 font-brand text-xs font-bold uppercase tracking-[0.14em] text-muted">Filter by year</p>

      {/* bar track + inputs */}
      <div ref={containerRef} className="relative pt-7">

        {/* glow behind bars */}
        <div
          className="pointer-events-none absolute bottom-0 rounded-full blur-xl"
          style={{
            left: `${gloLo}%`,
            width: `${gloHi - gloLo}%`,
            height: "100%",
            background: "radial-gradient(ellipse at 50% 100%, rgba(17,24,33,0.12) 0%, transparent 75%)",
          }}
        />

        {/* bars */}
        <div className="relative flex h-12 items-end justify-between pointer-events-none">
          {bars.map(({ height, color, opacity, glow }, i) => (
            <div
              key={i}
              className="rounded-[2px]"
              style={{
                width: 7,
                height: `${height}%`,
                opacity,
                background: color,
                boxShadow: glow,
                transition: "height 0.1s ease, background 0.1s ease, box-shadow 0.1s ease",
              }}
            />
          ))}
        </div>

        {/* boundary line markers */}
        {([gloLo, gloHi] as const).map((pos, i) => (
          <div key={i} className="pointer-events-none absolute" style={{ left: `${pos}%`, top: -8, bottom: -4, transform: "translateX(-50%)", display: "flex", flexDirection: "column", alignItems: "center", gap: 0, zIndex: 15 }}>
            {/* year pill */}
            <span className="mb-1 -translate-x-0 rounded-full bg-ink px-2 py-[2px] font-brand text-[11px] font-bold text-white shadow" style={{ whiteSpace: "nowrap" }}>
              {i === 0 ? value[0] : value[1]}
            </span>
            {/* vertical divider line */}
            <div className="flex-1 rounded-full" style={{ width: 2, background: "var(--color-ink)", opacity: 0.8 }} />
          </div>
        ))}

        {/* lo range input */}
        <input
          type="range" min={min} max={max} step={1} value={value[0]}
          onChange={handleLo}
          onPointerDown={() => setFront("lo")}
          className="year-range-input absolute inset-0 w-full"
          style={{ zIndex: front === "lo" ? 30 : 20 }}
        />

        {/* hi range input */}
        <input
          type="range" min={min} max={max} step={1} value={value[1]}
          onChange={handleHi}
          onPointerDown={() => setFront("hi")}
          className="year-range-input absolute inset-0 w-full"
          style={{ zIndex: front === "hi" ? 30 : 20 }}
        />
      </div>

      {/* min / max labels */}
      <div className="mt-2 flex justify-between font-brand text-[11px] text-muted">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  )
}
