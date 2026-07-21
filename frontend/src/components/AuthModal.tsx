import { useState } from "react"
import { X } from "lucide-react"

export type CurrentUser = { id: string; username: string }

interface Props {
  initialTab?: "login" | "signup"
  onSuccess: (user: CurrentUser) => void
  onClose: () => void
}

export function AuthModal({ initialTab = "login", onSuccess, onClose }: Props) {
  const [tab, setTab] = useState<"login" | "signup">(initialTab)
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    const u = username.trim()
    const p = password.trim()
    if (!u || !p) { setError("Fill in all fields."); return }
    setLoading(true); setError("")
    const url = tab === "login" ? "/api/auth/login" : "/api/auth/signup"
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p }),
    })
    const data = await res.json()
    setLoading(false)
    if (!res.ok) {
      setError(data.detail ?? "Something went wrong.")
      return
    }
    onSuccess(data as CurrentUser)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-2xl border border-line bg-white p-6 shadow-[0_20px_60px_rgba(28,38,63,.18)]">
        <div className="mb-5 flex items-center justify-between">
          <div className="flex gap-1 rounded-xl bg-page p-1">
            {(["login", "signup"] as const).map(t => (
              <button
                key={t}
                onClick={() => { setTab(t); setError("") }}
                className={`rounded-lg px-4 py-1.5 text-sm font-semibold transition-colors ${tab === t ? "bg-white text-ink shadow-sm" : "text-muted hover:text-ink"}`}
              >
                {t === "login" ? "Log in" : "Sign up"}
              </button>
            ))}
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted transition-colors hover:bg-page hover:text-ink">
            <X className="size-4" />
          </button>
        </div>

        <div className="flex flex-col gap-3">
          <input
            autoFocus
            value={username}
            onChange={e => setUsername(e.target.value)}
            onKeyDown={e => e.key === "Enter" && submit()}
            placeholder="Username"
            className="rounded-lg border border-line bg-page px-3 py-2.5 text-sm text-ink outline-none placeholder:text-muted focus:border-brand focus:ring-1 focus:ring-brand"
          />
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && submit()}
            placeholder="Password"
            className="rounded-lg border border-line bg-page px-3 py-2.5 text-sm text-ink outline-none placeholder:text-muted focus:border-brand focus:ring-1 focus:ring-brand"
          />
          {error && <p className="text-xs text-red-500">{error}</p>}
          <button
            onClick={submit}
            disabled={loading}
            className="rounded-xl bg-brand py-2.5 font-brand text-sm font-extrabold text-white transition-opacity disabled:opacity-50 hover:bg-brand/90"
          >
            {loading ? "…" : tab === "login" ? "Log in" : "Create account"}
          </button>
        </div>
      </div>
    </div>
  )
}
