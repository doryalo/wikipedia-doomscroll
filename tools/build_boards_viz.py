#!/usr/bin/env python3
"""Generate tasks/boards_viz.html — a single, self-contained kanban viewer.

Reads:  .forge/project-pack.yaml  (roles / boards / skills_dir)
        tasks/<board_file>.json   (per-role task boards)
        .forge/runs/<id>/*.md     (run-log entries per task)
        <skills_dir>/<skill>.md   (agent capability bullets)
        .forge/usage.jsonl        (optional token usage)

Writes: tasks/boards_viz.html    (double-click, no server needed)

Stdlib-only, Python 3.9+. Drop this file into any forge-scaffolded repo.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (resolved relative to this file's parent = project root)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
FORGE_DIR = REPO_ROOT / ".forge"
RUNS_DIR  = FORGE_DIR / "runs"
USAGE_FILE = FORGE_DIR / "usage.jsonl"
OUT_FILE  = TASKS_DIR / "boards_viz.html"

# ---------------------------------------------------------------------------
# Pack loading (inline — no agent_forge import)
# ---------------------------------------------------------------------------

def _load_pack() -> dict:
    pack_path = FORGE_DIR / "project-pack.yaml"
    if not pack_path.is_file():
        sys.exit(f"[build_boards_viz] No pack at {pack_path}. Run forge adapt first.")
    try:
        import yaml  # type: ignore[import]
        raw = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    except ImportError:
        # Fallback minimal YAML parser for version/project_name/roles (no anchors needed)
        raw = _parse_simple_yaml(pack_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        sys.exit(f"[build_boards_viz] Invalid pack: {pack_path}")
    return raw


def _parse_simple_yaml(text: str) -> dict:
    """Minimal line-by-line YAML parser for project-pack.yaml format.

    Extracts the fields actually used by this script: project_name, skills_dir,
    and the roles list (name/prefix/board_file/skill per role).
    Handles: block scalars, block sequences of mappings, nested lists, flow lists.
    Does NOT handle: anchors, multi-line folded/literal scalars, complex flow mappings.
    """
    result: dict = {}

    def _scalar(s: str):
        s = s.strip()
        if not s or s in ("null", "~"):
            return None
        if s == "true":
            return True
        if s == "false":
            return False
        try:
            return int(s)
        except ValueError:
            pass
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
            return s[1:-1]
        return s

    def _flow_list(v: str) -> list:
        inner = v.strip().lstrip("[").rstrip("]")
        return [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]

    def _indent(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    lines = text.splitlines()
    section: str | None = None
    is_roles = False
    role: dict | None = None
    role_sublist: str | None = None

    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        ind = _indent(raw)

        # inside a role block
        if is_roles and role is not None and ind > 0:
            if stripped.startswith("- ") and role_sublist is not None:
                role[role_sublist].append(_scalar(stripped[2:]))
            elif ":" in stripped and not stripped.startswith("- "):
                k, _, v = stripped.partition(":")
                k = k.strip(); v = v.strip()
                role_sublist = None
                if v:
                    role[k] = _flow_list(v) if v.startswith("[") else _scalar(v)
                else:
                    role_sublist = k
                    role[k] = []
            continue

        # new role item
        if is_roles and ind == 0 and stripped.startswith("- "):
            if role is not None:
                result["roles"].append(role)
            rest = stripped[2:].strip()
            role = {}
            role_sublist = None
            if rest and ":" in rest:
                k, _, v = rest.partition(":")
                role[k.strip()] = _scalar(v)
            continue

        # top-level list item (non-roles section)
        if section and not is_roles and ind == 0 and stripped.startswith("- "):
            if section not in result:
                result[section] = []
            result[section].append(_scalar(stripped[2:]))
            continue

        # top-level key: value
        if ind == 0 and ":" in stripped and not stripped.startswith("- "):
            if is_roles and role is not None:
                result["roles"].append(role)
                role = None
                role_sublist = None
            is_roles = False
            section = None
            k, _, v = stripped.partition(":")
            k = k.strip(); v = v.strip()
            if v:
                result[k] = _flow_list(v) if v.startswith("[") else _scalar(v)
            else:
                section = k
                if k == "roles":
                    result["roles"] = []
                    is_roles = True
                else:
                    result[k] = []

    if is_roles and role is not None:
        result["roles"].append(role)

    return result


# ---------------------------------------------------------------------------
# Board loading
# ---------------------------------------------------------------------------

def load_boards(pack: dict) -> list[dict]:
    roles = pack.get("roles", [])
    boards = []
    for role in roles:
        name       = role.get("name", "unknown")
        prefix     = role.get("prefix", "??")
        board_file = role.get("board_file", f"{name}.json")
        path       = TASKS_DIR / board_file
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                tasks = data.get("tasks", [])
                updated_at = data.get("updated_at", "")
            except Exception as exc:
                print(f"[warn] Failed to parse {path}: {exc}", file=sys.stderr)
                tasks = []
                updated_at = ""
        else:
            print(f"[warn] Board not found: {path}", file=sys.stderr)
            tasks = []
            updated_at = ""
        boards.append({
            "team": name,
            "prefix": prefix,
            "file": str(path.relative_to(REPO_ROOT)),
            "updated_at": updated_at,
            "tasks": tasks,
        })
    return boards


# ---------------------------------------------------------------------------
# Run-log parsing
# ---------------------------------------------------------------------------

_FNAME_RE = re.compile(
    r"^(?P<stamp>\d{8}T\d{6}_\d+)__(?P<flow>.+?)__(?P<agent>.+)\.md$"
)
_HEADER_RE = re.compile(r"^-\s+\*\*(?P<key>[^:]+):\*\*\s*(?P<val>.*)$")


def _parse_stamp(s: str) -> str:
    try:
        dt = datetime.strptime(s[:15], "%Y%m%dT%H%M%S")
        frac = s[16:] if len(s) > 16 else "0"
        return dt.replace(microsecond=int(frac[:6].ljust(6, "0")),
                          tzinfo=timezone.utc).isoformat()
    except Exception:
        return s


def parse_log_file(path: Path, stamp: str, flow: str, agent: str) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    entry: dict = {
        "ts": _parse_stamp(stamp),
        "flow": flow,
        "agent": agent,
        "verdict": "",
        "reason": "",
        "response": "",
        "tokens": {},
        "transcript_file": "",
        "raw": text,
    }
    section = ""
    response_lines: list[str] = []
    for line in text.splitlines():
        m = _HEADER_RE.match(line)
        if m:
            k, v = m.group("key").strip().lower().replace(" ", "_"), m.group("val").strip()
            if k in ("verdict", "reason", "transcript_file"):
                entry[k] = v
            elif k == "token_usage":
                try:
                    entry["tokens"] = json.loads(v)
                except Exception:
                    pass
            continue
        stripped = line.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip().lower()
            continue
        if section == "response":
            response_lines.append(line)
    entry["response"] = "\n".join(response_lines).strip()
    return entry


def load_run_logs(boards: list[dict]) -> dict[str, list[dict]]:
    task_ids: set[str] = set()
    for board in boards:
        for task in board["tasks"]:
            tid = task.get("id", "")
            if tid:
                task_ids.add(tid)

    logs: dict[str, list[dict]] = {}
    if not RUNS_DIR.is_dir():
        return logs

    for task_dir in RUNS_DIR.iterdir():
        if not task_dir.is_dir():
            continue
        task_id = task_dir.name
        entries = []
        for fpath in sorted(task_dir.glob("*.md")):
            m = _FNAME_RE.match(fpath.name)
            if not m:
                continue
            try:
                entry = parse_log_file(fpath, m.group("stamp"), m.group("flow"), m.group("agent"))
                entries.append(entry)
            except Exception as exc:
                print(f"[warn] Failed to parse {fpath}: {exc}", file=sys.stderr)
        if entries:
            entries.sort(key=lambda e: e["ts"])
            logs[task_id] = entries

    return logs


# ---------------------------------------------------------------------------
# Token usage aggregation
# ---------------------------------------------------------------------------

_USAGE_FIELDS = ("input_tokens", "output_tokens", "total_tokens", "cache_read", "cache_creation")


def load_usage() -> dict[str, dict]:
    usage: dict[str, dict] = {}
    if not USAGE_FILE.is_file():
        return usage
    for line in USAGE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        task_id = rec.get("task_id", "")
        if not task_id:
            continue
        u = rec.get("usage", {})
        if task_id not in usage:
            usage[task_id] = {"models": {}, "stages": []}
        for model, vals in u.items():
            if model not in usage[task_id]["models"]:
                usage[task_id]["models"][model] = {f: 0 for f in _USAGE_FIELDS}
            for f in _USAGE_FIELDS:
                usage[task_id]["models"][model][f] += vals.get(f, 0)
        stage_entry = {
            "role": rec.get("role", ""),
            "flow": rec.get("flow", ""),
            "ts":   rec.get("ts", ""),
            "models": u,
        }
        usage[task_id]["stages"].append(stage_entry)
    return usage


# ---------------------------------------------------------------------------
# Agent info from skill files
# ---------------------------------------------------------------------------

_FRONT_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def _extract_role(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _extract_capability_bullets(text: str, limit: int = 6) -> list[str]:
    body = _FRONT_RE.sub("", text, count=1)
    bullets: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# "):
            continue
        if s.startswith(("## ", "### ", "#### ")):
            bullets.append(s.lstrip("# ").strip())
        elif s.startswith(("- ", "* ")):
            bullets.append(s[2:].strip())
        if len(bullets) >= limit:
            break
    return bullets


def load_agents(pack: dict) -> dict[str, dict]:
    skills_dir_rel = pack.get("skills_dir", ".claude/commands")
    skills_dir = REPO_ROOT / skills_dir_rel
    roles = pack.get("roles", [])
    agents: dict[str, dict] = {}
    for role in roles:
        skill  = role.get("skill", role.get("name", ""))
        prefix = role.get("prefix", "??")
        name   = role.get("name", "")
        skill_path = skills_dir / f"{skill}.md"
        if skill_path.is_file():
            text = skill_path.read_text(encoding="utf-8", errors="replace")
            role_label = _extract_role(text) or name
            bullets = _extract_capability_bullets(text)
            lines = len(text.splitlines())
        else:
            role_label = name
            bullets = []
            lines = 0
            text = ""
        agents[skill] = {
            "skill": skill,
            "role": role_label,
            "board_prefix": prefix,
            "capability_bullets": bullets,
            "lines": lines,
        }
    return agents


# ---------------------------------------------------------------------------
# Embed helper
# ---------------------------------------------------------------------------

def _embed(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ — Boards</title>
<style>
:root {
  --bg:#0d1117; --bg2:#161b22; --bg3:#21262d;
  --border:#30363d; --text:#e6edf3; --muted:#8b949e; --accent:#58a6ff;
  --st-pending:#8b949e; --st-in_progress:#58a6ff; --st-review:#d2a8ff;
  --st-done:#3fb950; --st-blocked:#f85149; --st-cancelled:#8b949e;
  --st-skipped:#8b949e;
  --vd-accept:#3fb950; --vd-reject:#f85149; --vd-neutral:#8b949e;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:ui-sans-serif,system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column}
a{color:var(--accent)}
/* header */
.hdr{padding:12px 20px;background:var(--bg2);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:50}
.hdr h1{font-size:16px;font-weight:700}
.chip{font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid var(--border);color:var(--muted)}
.chip.pending{border-color:var(--st-pending);color:var(--st-pending)}
.chip.in_progress{border-color:var(--st-in_progress);color:var(--st-in_progress)}
.chip.done{border-color:var(--st-done);color:var(--st-done)}
.chip.blocked{border-color:var(--st-blocked);color:var(--st-blocked)}
.gen-ts{margin-left:auto;font-size:11px;color:var(--muted)}
/* tab bar */
.tabs-bar{display:flex;gap:4px;background:var(--bg3);padding:3px;border-radius:8px;margin:0 20px 0 0}
.tab-btn{padding:5px 12px;border-radius:6px;cursor:pointer;font-size:13px;color:var(--muted);user-select:none;border:none;background:transparent}
.tab-btn.active{background:var(--accent);color:#04101f;font-weight:700}
/* controls */
.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:10px 20px;border-bottom:1px solid var(--border);background:var(--bg2)}
.controls label{font-size:12px;color:var(--muted)}
select,input[type=search]{background:var(--bg3);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:5px 8px;font-size:13px;outline:none}
input[type=search]{min-width:180px}
/* board view */
#boardView{padding:16px 20px;overflow-x:auto}
.boards{display:flex;gap:14px;align-items:flex-start;min-height:200px}
.board{flex:0 0 300px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;display:flex;flex-direction:column;max-height:calc(100vh - 270px)}
.board-head{padding:9px 12px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px}
.board-head .bname{font-weight:600;font-size:13px}
.board-head .bprefix{font-size:11px;background:var(--bg3);border:1px solid var(--border);padding:1px 6px;border-radius:4px;color:var(--muted)}
.board-head .bcount{margin-left:auto;color:var(--muted);font-size:12px}
.board-body{padding:10px;overflow-y:auto;display:flex;flex-direction:column;gap:8px}
.empty{color:var(--muted);font-size:12px;font-style:italic;padding:14px;text-align:center}
/* card */
.card{background:var(--bg3);border:1px solid var(--border);border-left:4px solid var(--st-pending);border-radius:8px;padding:10px;cursor:pointer;transition:transform .08s}
.card:hover{transform:translateY(-1px);border-color:var(--accent)}
.card.dim{opacity:.25}
.card-top{display:flex;align-items:center;gap:6px;margin-bottom:5px}
.card-id{font-family:ui-monospace,monospace;font-size:11px;color:var(--accent);font-weight:700}
.pill{font-size:10px;padding:1px 7px;border-radius:999px;text-transform:uppercase;letter-spacing:.4px;font-weight:700;color:#04101f}
.prio{margin-left:auto;font-size:10px;font-weight:700;padding:1px 7px;border-radius:4px;border:1px solid var(--border)}
.card-title{font-size:13px;line-height:1.35;margin-bottom:5px}
.card-meta{display:flex;flex-wrap:wrap;gap:5px;align-items:center;font-size:11px;color:var(--muted)}
.tag{background:#21262d;border:1px solid var(--border);border-radius:4px;padding:0 5px;font-size:10px}
.runbadge{font-size:10px;font-weight:700;color:var(--accent);background:rgba(88,166,255,.12);border:1px solid rgba(88,166,255,.4);border-radius:999px;padding:0 7px}
/* drawer */
#drawer{position:fixed;top:0;right:0;height:100%;width:480px;max-width:94vw;background:var(--bg2);border-left:1px solid var(--border);transform:translateX(100%);transition:transform .2s;z-index:100;overflow-y:auto;box-shadow:-8px 0 24px rgba(0,0,0,.4)}
#drawer.open{transform:translateX(0)}
.drawer-head{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px;position:sticky;top:0;background:var(--bg2);z-index:2}
.drawer-head .close{margin-left:auto;cursor:pointer;color:var(--muted);font-size:20px;line-height:1}
.drawer-body{padding:16px}
.drawer-body h2{font-size:15px;margin:0 0 12px}
.drawer-body section{margin-bottom:16px}
.drawer-body section h5{margin:0 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted)}
.drawer-body p{margin:0;line-height:1.5;white-space:pre-wrap;color:#c9d1d9;font-size:13px}
/* timeline */
.timeline{list-style:none;padding:0 0 0 6px;position:relative}
.tl-item{position:relative;padding:0 0 14px 22px}
.tl-item::before{content:"";position:absolute;left:5px;top:4px;bottom:-4px;width:2px;background:var(--border)}
.tl-item:last-child::before{bottom:auto;height:14px}
.tl-dot{position:absolute;left:0;top:3px;width:12px;height:12px;border-radius:50%;border:2px solid var(--bg2);z-index:1}
.tl-head{display:flex;align-items:center;gap:6px;flex-wrap:wrap;cursor:pointer}
.tl-agent{font-size:11px;font-weight:700;padding:1px 8px;border-radius:999px;color:#04101f}
.tl-flow{font-size:10px;color:var(--muted);font-family:ui-monospace,monospace}
.tl-verdict{font-size:10px;font-weight:700;padding:1px 8px;border-radius:999px;text-transform:uppercase;letter-spacing:.3px;color:#04101f}
.tl-time{margin-left:auto;font-size:10px;color:var(--muted);font-family:ui-monospace,monospace}
.tl-reason{margin:5px 0 0;font-size:12px;color:#c9d1d9;line-height:1.45}
.tl-toggle{margin-top:6px;font-size:11px;color:var(--accent);cursor:pointer;user-select:none;display:inline-flex;align-items:center;gap:4px}
.tl-resp{display:none;margin-top:8px}
.tl-item.open .tl-resp{display:block}
.md{background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:10px 12px;font-size:12.5px;line-height:1.55;color:#c9d1d9;overflow-x:auto}
.md h1,.md h2,.md h3,.md h4{margin:10px 0 6px;color:var(--text)}
.md p{margin:6px 0;white-space:normal}
.md ul,.md ol{margin:6px 0;padding-left:20px}
.md code{font-family:ui-monospace,monospace;font-size:11.5px;background:#0d1117;border:1px solid var(--border);border-radius:4px;padding:0 4px}
.md pre{background:#0d1117;border:1px solid var(--border);border-radius:6px;padding:10px;overflow-x:auto;margin:8px 0}
.md pre code{background:none;border:none;padding:0}
/* usage */
.usage-block>summary{cursor:pointer;list-style:none;user-select:none;font-size:13px;font-weight:600;color:var(--text);padding:8px 10px;background:var(--bg3);border:1px solid var(--border);border-radius:6px}
.usage-block>summary::before{content:"\25B8 ";color:var(--muted)}
.usage-block[open]>summary::before{content:"\25BE "}
.usage-tbl{width:100%;border-collapse:collapse;margin-top:8px;font-size:12px}
.usage-tbl th,.usage-tbl td{text-align:right;padding:4px 8px;border-bottom:1px solid var(--border)}
.usage-tbl th{color:var(--muted);font-weight:500}
.usage-tbl th:first-child,.usage-tbl td:first-child{text-align:left}
.usage-tbl .um-model{font-family:ui-monospace,monospace;color:var(--accent)}
/* agents tab */
#agentsView{display:none;padding:16px 20px}
#agentsView.active{display:block}
.agent-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.agent-card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:14px}
.agent-card h3{font-size:14px;margin-bottom:4px}
.agent-card .a-prefix{font-size:11px;color:var(--muted);margin-bottom:8px}
.agent-card ul{list-style:none;font-size:12px;color:#c9d1d9;display:flex;flex-direction:column;gap:4px}
.agent-card ul li::before{content:"\2022 ";color:var(--accent)}
/* backdrop */
#backdrop{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:90;display:none}
#backdrop.open{display:block}
/* toast */
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%) translateY(10px);background:var(--bg2);border:1px solid var(--accent);color:var(--text);border-radius:8px;padding:10px 16px;font-size:13px;z-index:200;opacity:0;pointer-events:none;transition:opacity .2s,transform .2s}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style>
</head>
<body>

<div class="hdr">
  <h1 id="projTitle">__TITLE__</h1>
  <span class="chip pending" id="cntPending">0 pending</span>
  <span class="chip in_progress" id="cntProg">0 in progress</span>
  <span class="chip done" id="cntDone">0 done</span>
  <span class="chip blocked" id="cntBlocked">0 blocked</span>
  <div class="tabs-bar">
    <button class="tab-btn active" onclick="switchTab('boards')">Boards</button>
    <button class="tab-btn" onclick="switchTab('agents')">Agents</button>
  </div>
  <span class="gen-ts">Generated __GEN_TS__</span>
</div>

<div class="controls" id="controls">
  <label>Status
    <select id="statusFilter" onchange="render()">
      <option value="">All</option>
      <option value="pending">Pending</option>
      <option value="in_progress">In Progress</option>
      <option value="review">Review</option>
      <option value="done">Done</option>
      <option value="blocked">Blocked</option>
    </select>
  </label>
  <label>Search
    <input type="search" id="searchBox" placeholder="id or title…" oninput="render()">
  </label>
</div>

<div id="boardView"><div class="boards" id="boardsContainer"></div></div>
<div id="agentsView"><div class="agent-grid" id="agentGrid"></div></div>

<div id="backdrop" onclick="closeDrawer()"></div>
<div id="drawer">
  <div class="drawer-head">
    <span id="drwId" class="card-id"></span>
    <span id="drwVerdict" class="tl-verdict"></span>
    <span class="close" onclick="closeDrawer()">&#x2715;</span>
  </div>
  <div class="drawer-body" id="drawerBody"></div>
</div>

<div class="toast" id="toast"></div>

<script>
const BOARDS = __BOARDS__;
const RUN_LOGS = __RUN_LOGS__;
const AGENTS = __AGENTS__;
const USAGE = __USAGE__;
const TITLE = __TITLE_JSON__;

// ---------------------------------------------------------------------------
// Status / priority helpers
// ---------------------------------------------------------------------------
const STATUS_COLORS = {
  pending:'var(--st-pending)', in_progress:'var(--st-in_progress)',
  review:'var(--st-review)', done:'var(--st-done)',
  blocked:'var(--st-blocked)', cancelled:'var(--st-cancelled)', skipped:'var(--st-skipped)',
};
const VERDICT_COLORS = {
  accept:'var(--vd-accept)', reject:'var(--vd-reject)', neutral:'var(--vd-neutral)',
};
const PRIO_COLORS = {'critical':'#f85149','high':'#d2a8ff','medium':'#e3b341','low':'var(--muted)'};

function stColor(st){ return STATUS_COLORS[st] || 'var(--muted)'; }
function vdColor(v){ return VERDICT_COLORS[(v||'').toLowerCase()] || 'var(--muted)'; }

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
let activeTab = 'boards';
function switchTab(t){
  activeTab = t;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.textContent.toLowerCase()===t));
  document.getElementById('boardView').style.display = t==='boards' ? '' : 'none';
  document.getElementById('agentsView').classList.toggle('active', t==='agents');
  document.getElementById('controls').style.display = t==='boards' ? '' : 'none';
  if(t==='agents') renderAgents();
}

// ---------------------------------------------------------------------------
// Board rendering
// ---------------------------------------------------------------------------
function getAllTasks(){
  const tasks = [];
  for(const b of BOARDS) for(const t of b.tasks) tasks.push({...t, _board:b});
  return tasks;
}

function countByStatus(){
  const c = {pending:0, in_progress:0, done:0, blocked:0};
  getAllTasks().forEach(t => { if(c[t.status]!==undefined) c[t.status]++; });
  return c;
}

function render(){
  const statusF = document.getElementById('statusFilter').value;
  const searchF = document.getElementById('searchBox').value.toLowerCase();
  const counts = countByStatus();
  document.getElementById('cntPending').textContent = counts.pending + ' pending';
  document.getElementById('cntProg').textContent = counts.in_progress + ' in progress';
  document.getElementById('cntDone').textContent = counts.done + ' done';
  document.getElementById('cntBlocked').textContent = counts.blocked + ' blocked';

  const container = document.getElementById('boardsContainer');
  container.innerHTML = '';
  for(const board of BOARDS){
    const col = document.createElement('div');
    col.className = 'board';
    const tasks = board.tasks;
    let html = `<div class="board-head"><span class="bname">${esc(board.team)}</span><span class="bprefix">${esc(board.prefix)}</span><span class="bcount">${tasks.length}</span></div><div class="board-body">`;
    let shown = 0;
    for(const t of tasks){
      const match = (!statusF || t.status===statusF) &&
                    (!searchF || t.id.toLowerCase().includes(searchF) || (t.title||'').toLowerCase().includes(searchF));
      const dim = !match && (statusF||searchF) ? ' dim' : '';
      const rlogs = RUN_LOGS[t.id] || [];
      const runBadge = rlogs.length ? `<span class="runbadge">${rlogs.length} run${rlogs.length>1?'s':''}</span>` : '';
      const prio = t.priority ? `<span class="prio" style="color:${PRIO_COLORS[t.priority]||'var(--muted)'}">${esc(t.priority)}</span>` : '';
      const tags = (t.tags||[]).map(g=>`<span class="tag">${esc(g)}</span>`).join('');
      const assignee = t.assignee ? `<span class="assignee">@${esc(t.assignee)}</span>` : '';
      html += `<div class="card${dim}" onclick="openDrawer(${JSON.stringify(t.id)},${JSON.stringify(board.prefix)})" style="border-left-color:${stColor(t.status)}">
        <div class="card-top"><span class="card-id">${esc(t.id)}</span><span class="pill" style="background:${stColor(t.status)}">${esc(t.status)}</span>${prio}${runBadge}</div>
        <div class="card-title">${esc(t.title||'(no title)')}</div>
        <div class="card-meta">${assignee}${tags}</div>
      </div>`;
      shown++;
    }
    if(!shown && !tasks.length) html += '<div class="empty">No tasks</div>';
    html += '</div>';
    col.innerHTML = html;
    container.appendChild(col);
  }
}

// ---------------------------------------------------------------------------
// Drawer
// ---------------------------------------------------------------------------
let openTaskId = null;

function openDrawer(taskId, prefix){
  openTaskId = taskId;
  let task = null, board = null;
  for(const b of BOARDS){ const t = b.tasks.find(x=>x.id===taskId); if(t){task=t; board=b; break;} }
  if(!task) return;

  document.getElementById('drwId').textContent = taskId;
  const vEl = document.getElementById('drwVerdict');
  vEl.textContent = task.status || '';
  vEl.style.background = stColor(task.status);

  let html = `<h2>${esc(task.title||'')}</h2>`;

  // Metadata
  html += `<section><h5>Details</h5><div style="font-size:13px;color:#c9d1d9;display:flex;flex-direction:column;gap:4px">`;
  if(task.priority) html += `<div><b style="color:var(--muted)">Priority:</b> <span style="color:${PRIO_COLORS[task.priority]||'var(--text)'}">${esc(task.priority)}</span></div>`;
  if(task.assignee) html += `<div><b style="color:var(--muted)">Assignee:</b> ${esc(task.assignee)}</div>`;
  if((task.tags||[]).length) html += `<div><b style="color:var(--muted)">Tags:</b> ${task.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join(' ')}</div>`;
  html += '</div></section>';

  if(task.description) html += `<section><h5>Description</h5><p>${esc(task.description)}</p></section>`;
  if((task.acceptance_criteria||[]).length){
    html += `<section><h5>Acceptance Criteria</h5><ul style="list-style:none;display:flex;flex-direction:column;gap:4px">`;
    for(const ac of task.acceptance_criteria) html += `<li style="font-size:13px;color:#c9d1d9;padding-left:16px;position:relative"><span style="position:absolute;left:0;color:var(--st-done)">✓</span>${esc(ac)}</li>`;
    html += '</ul></section>';
  }
  if((task.subtasks||[]).length){
    const done = task.subtasks.filter(s=>s.status==='done').length;
    html += `<section><h5>Subtasks (${done}/${task.subtasks.length})</h5><ul style="list-style:none;display:flex;flex-direction:column;gap:6px">`;
    for(const s of task.subtasks) html += `<li style="background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:7px;font-size:12px"><span style="color:${stColor(s.status)};font-weight:700">${esc(s.id||'')}</span> ${esc(s.title||'')} <span style="float:right;color:var(--muted)">${esc(s.status||'')}</span></li>`;
    html += '</ul></section>';
  }
  if((task.depends_on||[]).length){
    html += `<section><h5>Dependencies</h5><div style="display:flex;flex-wrap:wrap;gap:6px">`;
    for(const d of task.depends_on) html += `<span onclick="openDrawer(${JSON.stringify(d)},null)" style="font-family:ui-monospace,monospace;background:#21262d;border:1px solid var(--accent);border-radius:4px;padding:0 6px;cursor:pointer;color:var(--accent);font-size:12px">${esc(d)}</span>`;
    html += '</div></section>';
  }

  // Run log timeline
  const logs = RUN_LOGS[taskId] || [];
  if(logs.length){
    html += `<section><h5>Run History (${logs.length})</h5><ul class="timeline">`;
    for(let i=0; i<logs.length; i++){
      const e = logs[i];
      const vd = (e.verdict||'').toLowerCase();
      const dot_color = VERDICT_COLORS[vd] || 'var(--muted)';
      const ts_short = e.ts ? e.ts.slice(11,19) : '';
      const resp_id = `resp_${taskId}_${i}`;
      html += `<li class="tl-item" id="tl_${resp_id}">
        <div class="tl-dot" style="background:${dot_color}"></div>
        <div class="tl-head" onclick="toggleResp(${JSON.stringify(resp_id)})">
          <span class="tl-agent" style="background:var(--accent)">${esc(e.agent)}</span>
          <span class="tl-flow">${esc(e.flow)}</span>
          ${e.verdict ? `<span class="tl-verdict" style="background:${vdColor(e.verdict)}">${esc(e.verdict)}</span>` : ''}
          <span class="tl-time">${ts_short}</span>
        </div>
        ${e.reason ? `<div class="tl-reason">${esc(e.reason)}</div>` : ''}
        ${e.response ? `<div class="tl-toggle" onclick="toggleResp(${JSON.stringify(resp_id)})"><span class="caret">&#x25B8;</span> Response</div><div class="tl-resp"><div class="md">${renderMd(e.response)}</div></div>` : ''}
      </li>`;
    }
    html += '</ul></section>';
  }

  // Usage
  const usg = USAGE[taskId];
  if(usg && Object.keys(usg.models||{}).length){
    html += `<section><details class="usage-block"><summary>Token Usage</summary>`;
    html += `<table class="usage-tbl"><thead><tr><th>Model</th><th>In</th><th>Out</th><th>Cache R</th><th>Total</th></tr></thead><tbody>`;
    for(const [model, vals] of Object.entries(usg.models)){
      html += `<tr><td class="um-model">${esc(model)}</td><td>${fmt(vals.input_tokens)}</td><td>${fmt(vals.output_tokens)}</td><td>${fmt(vals.cache_read)}</td><td>${fmt(vals.total_tokens)}</td></tr>`;
    }
    html += '</tbody></table></details></section>';
  }

  document.getElementById('drawerBody').innerHTML = html;
  document.getElementById('drawer').classList.add('open');
  document.getElementById('backdrop').classList.add('open');
}

function closeDrawer(){
  document.getElementById('drawer').classList.remove('open');
  document.getElementById('backdrop').classList.remove('open');
  openTaskId = null;
}

function toggleResp(id){
  document.getElementById('tl_' + id)?.classList.toggle('open');
}

// ---------------------------------------------------------------------------
// Agents tab
// ---------------------------------------------------------------------------
function renderAgents(){
  const grid = document.getElementById('agentGrid');
  grid.innerHTML = '';
  const agentList = Object.values(AGENTS);
  if(!agentList.length){ grid.innerHTML = '<div style="color:var(--muted);padding:20px">No agent info found. Check skills_dir in pack.</div>'; return; }
  for(const a of agentList){
    const bullets = (a.capability_bullets||[]).map(b=>`<li>${esc(b)}</li>`).join('');
    grid.innerHTML += `<div class="agent-card">
      <h3>${esc(a.role||a.skill)}</h3>
      <div class="a-prefix">Prefix: <b style="color:var(--accent)">${esc(a.board_prefix)}</b> &nbsp;·&nbsp; skill: <code>${esc(a.skill)}</code></div>
      ${bullets ? `<ul>${bullets}</ul>` : '<div style="color:var(--muted);font-size:12px">No bullets extracted.</div>'}
    </div>`;
  }
}

// ---------------------------------------------------------------------------
// Minimal markdown renderer (headings, bold, inline-code, paragraphs)
// ---------------------------------------------------------------------------
function renderMd(text){
  if(!text) return '';
  let html = esc(text);
  // headings
  html = html.replace(/^#### (.+)$/gm,'<h4>$1</h4>');
  html = html.replace(/^### (.+)$/gm,'<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm,'<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm,'<h1>$1</h1>');
  // bold/italic
  html = html.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g,'<em>$1</em>');
  // inline code
  html = html.replace(/`([^`]+)`/g,'<code>$1</code>');
  // newlines -> <br> (keep pre content as-is above already escaped)
  html = html.replace(/\n/g,'<br>');
  return html;
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function esc(s){ const d=document.createElement('div'); d.textContent=String(s||''); return d.innerHTML; }
function fmt(n){ if(!n) return '—'; if(n>=1e6) return (n/1e6).toFixed(1)+'M'; if(n>=1e3) return (n/1e3).toFixed(1)+'k'; return String(n); }
function toast(msg){ const el=document.getElementById('toast'); el.textContent=msg; el.classList.add('show'); setTimeout(()=>el.classList.remove('show'),2500); }

// keyboard
document.addEventListener('keydown', e => { if(e.key==='Escape') closeDrawer(); });

// init
document.getElementById('projTitle').textContent = TITLE;
render();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render_html(
    pack: dict,
    boards: list[dict],
    run_logs: dict[str, list[dict]],
    agents: dict[str, dict],
    usage: dict[str, dict],
) -> str:
    project_name = pack.get("project_name", "Project") or "Project"
    gen_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        HTML_TEMPLATE
        .replace("__TITLE__", project_name)
        .replace("__TITLE_JSON__", _embed(project_name))
        .replace("__GEN_TS__", gen_ts)
        .replace("__BOARDS__", _embed(boards))
        .replace("__RUN_LOGS__", _embed(run_logs))
        .replace("__AGENTS__", _embed(agents))
        .replace("__USAGE__", _embed(usage))
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    pack = _load_pack()
    boards = load_boards(pack)
    run_logs = load_run_logs(boards)
    agents = load_agents(pack)
    usage = load_usage()

    total_tasks = sum(len(b["tasks"]) for b in boards)
    total_runs  = sum(len(v) for v in run_logs.values())
    print(f"[build_boards_viz] {len(boards)} boards, {total_tasks} tasks, {total_runs} run-logs, {len(agents)} agents")

    html = render_html(pack, boards, run_logs, agents, usage)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"[build_boards_viz] Written {len(html):,} bytes → {OUT_FILE}")


if __name__ == "__main__":
    main()
