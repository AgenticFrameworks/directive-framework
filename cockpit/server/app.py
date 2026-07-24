#!/usr/bin/env python3
"""cockpit/server/app.py — the Directive Planner backend.

Serves the static cockpit frontend AND the six `/api/*` endpoints it depends on,
wiring the converse-to-converge planning loop into the framework's real runtime:
accepted decisions are written as paired PD/DD packets under a project's
`_directives/`, and `/api/gate` shells out to the canon `tools/gate-runner.py`
so the cockpit's "Run design-intake gate" button reports the true verdict.

Stdlib only — no third-party deps, matching the rest of `tools/`. The only
external call is `/api/chat`, which routes through OpenRouter
(`OPENROUTER_API_KEY` from the environment; per the model-provider policy the
default model is `owl-alpha`, with online models for research/deep probes).

Run:
    OPENROUTER_API_KEY=... python3 cockpit/server/app.py [--project DIR] [--port 5000]

The frontend bundle is served same-origin, so it reaches these endpoints at
`/api/*` with no CORS or base-URL configuration.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Paths — resolved from this file's location so the server is location-stable.
# ---------------------------------------------------------------------------
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
COCKPIT_DIR = os.path.dirname(SERVER_DIR)                 # .../cockpit
FRAMEWORK_ROOT = os.path.dirname(COCKPIT_DIR)             # repo root
GATE_RUNNER = os.path.join(FRAMEWORK_ROOT, "tools", "gate-runner.py")
INIT_RUNTIME = os.path.join(FRAMEWORK_ROOT, "tools", "init-runtime.py")
DESIGN_INTAKE_GATE = os.path.join(FRAMEWORK_ROOT, "gates", "design-intake.md")

# ---------------------------------------------------------------------------
# LLM provider surface (model-provider policy: OpenRouter first, owl-alpha default).
# ---------------------------------------------------------------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

# Two providers. Perplexity is direct (its Sonar models do the web search that
# powers research/deep probes and return citations); OpenRouter is the
# policy-default proxy (owl-alpha for plain chat, perplexity/sonar* for research).
# The active default is chosen at runtime by which key is present (see
# default_provider) — this honors an explicit Perplexity pin when only that key
# is set, per the model-provider policy's pinned-exception scope note.
PROVIDERS = {
    "perplexity": {
        "label": "Perplexity",
        "default": "sonar",
        "models": ["sonar", "sonar-pro", "sonar-reasoning"],
        "deep_model": "sonar-reasoning",
    },
    "openrouter": {
        "label": "OpenRouter",
        "default": "owl-alpha",
        "models": ["owl-alpha", "perplexity/sonar", "anthropic/claude-sonnet-4.6"],
        "deep_model": "perplexity/sonar-reasoning",
    },
}
PROVIDER_ENDPOINTS = {
    "perplexity": {"url": PERPLEXITY_URL, "key_env": "PERPLEXITY_API_KEY"},
    "openrouter": {"url": OPENROUTER_URL, "key_env": "OPENROUTER_API_KEY"},
}


def default_provider():
    """Pick the active provider. Honors COCKPIT_PROVIDER, else prefers whichever
    key is actually present (Perplexity pin first, then OpenRouter)."""
    override = os.environ.get("COCKPIT_PROVIDER")
    if override in PROVIDER_ENDPOINTS:
        return override
    if os.environ.get("PERPLEXITY_API_KEY"):
        return "perplexity"
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    return "perplexity"

SYSTEM_PROMPT = """\
You are the Directive Planner: a planning facilitator for the Directive Framework.
Converse with the user to converge one idea into a single ATOMIC, self-contained,
order-independent decision — the unit the framework calls a Decision Directive (DD).

Keep replies short and Socratic: surface the smallest unresolved question, weigh
alternatives, name the constraint that decides it. Do NOT propose until the scope
is genuinely settled to one concrete action.

When (and only when) a single atomic decision is ready, END your message with a
fenced code block tagged `proposal` containing minified JSON with EXACTLY these keys:
{"title":"imperative, names the action not a theme",
 "decision":"the concrete action for a context-starved consumer: exact paths, names, values",
 "rationale":"one line — why this decision was settled",
 "done_when":"an observable, checkable completion condition",
 "probes":["1-3 short verification probes"]}
Emit at most one proposal block per message. A DD must never be a broad theme
(e.g. 'Security Protocols'); if it would need its own research run, it is too broad.
"""

TS = "%Y-%m-%dT%H:%M:%SZ"
SERIAL_RE = re.compile(r"^(PD|DD)-(\d{3})")


def now_z():
    return datetime.datetime.now(datetime.timezone.utc).strftime(TS)


# ---------------------------------------------------------------------------
# Runtime packet I/O — the framework's source of truth lives in files.
# ---------------------------------------------------------------------------
class Runtime:
    """Owns all reads/writes of a project's `_directives/` planning packets."""

    def __init__(self, project, is_scratch):
        self.project = os.path.abspath(project)
        self.is_scratch = is_scratch
        self.root = os.path.join(self.project, "_directives")
        self.pd_dir = os.path.join(self.root, "PD")
        self.dd_dir = os.path.join(self.root, "DD")

    def ensure(self):
        """Idempotently seed `_directives/` via the canon init-runtime tool."""
        subprocess.run([sys.executable, INIT_RUNTIME, "--project", self.project],
                       cwd=FRAMEWORK_ROOT, capture_output=True, text=True)

    # -- parsing -----------------------------------------------------------
    @staticmethod
    def _split(text):
        """Return (frontmatter dict, body str). Frontmatter is the leading
        `---`-fenced block; values are kept as raw strings (probes decoded as JSON)."""
        fm, body = {}, text
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                block = text[3:end].strip("\n")
                body = text[end + 4:].lstrip("\n")
                for line in block.splitlines():
                    if ":" not in line:
                        continue
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
        return fm, body

    @staticmethod
    def _probes(fm):
        raw = fm.get("probes", "")
        if raw.startswith("["):
            try:
                val = json.loads(raw)
                if isinstance(val, list):
                    return [str(x) for x in val]
            except json.JSONDecodeError:
                pass
        return []

    def _packets(self, directory, kind):
        out = {}
        if not os.path.isdir(directory):
            return out
        for name in sorted(os.listdir(directory)):
            m = SERIAL_RE.match(name)
            if not m or m.group(1) != kind or not name.endswith(".md"):
                continue
            fm, body = self._split(_read(os.path.join(directory, name)))
            title = ""
            decision = body
            hm = re.search(r"^#\s+(.*)$", body, re.MULTILINE)
            if hm:
                title = hm.group(1).strip()
            dm = re.split(r"\n\s*Rationale:", body, maxsplit=1)
            if hm:
                decision = dm[0].split(hm.group(0), 1)[-1].strip()
            out[fm.get("id", "")] = {
                "id": fm.get("id", ""),
                "pair": fm.get("pair", ""),
                "status": fm.get("status", "draft"),
                "title": title,
                "body": decision,
                "probes": self._probes(fm),
            }
        return out

    def next_serial(self):
        serials = [0]
        for d, k in ((self.pd_dir, "PD"), (self.dd_dir, "DD")):
            if not os.path.isdir(d):
                continue
            for name in os.listdir(d):
                m = SERIAL_RE.match(name)
                if m:
                    serials.append(int(m.group(2)))
        n = max(serials) + 1
        if n > 999:
            raise ValueError("serial space exhausted (>999)")
        return f"{n:03d}"

    def find_by_source(self, key):
        """Idempotency: return the existing DD id whose `source` matches, or None."""
        marker = f"cockpit:{key}"
        if not os.path.isdir(self.dd_dir):
            return None
        for name in os.listdir(self.dd_dir):
            if not SERIAL_RE.match(name) or not name.endswith(".md"):
                continue
            fm, _ = self._split(_read(os.path.join(self.dd_dir, name)))
            if fm.get("source") == marker:
                return fm.get("id"), fm.get("pair")
        return None

    def board(self):
        cursor = {}
        cpath = os.path.join(self.root, "cursor.json")
        if os.path.isfile(cpath):
            try:
                cursor = json.loads(_read(cpath))
            except json.JSONDecodeError:
                cursor = {}
        pd = self._packets(self.pd_dir, "PD")
        dd = self._packets(self.dd_dir, "DD")
        return {
            "cursor": {"phase": cursor.get("phase", "planning")},
            "phases": {"DD": list(dd.values()), "PD": list(pd.values())},
        }

    def counts(self):
        return {
            "DD": len(self._packets(self.dd_dir, "DD")),
            "PD": len(self._packets(self.pd_dir, "PD")),
        }

    # -- writes ------------------------------------------------------------
    def accept(self, proposal):
        title = (proposal.get("title") or "").strip()
        decision = (proposal.get("decision") or "").strip()
        rationale = (proposal.get("rationale") or "").strip()
        done_when = (proposal.get("done_when") or "").strip()
        probes = [str(p) for p in (proposal.get("probes") or [])]
        if not title or not decision:
            return {"ok": False, "error": "proposal missing title/decision"}

        key = hashlib.sha1(f"{title}\x00{decision}".encode()).hexdigest()[:12]
        existing = self.find_by_source(key)
        if existing:
            return {"ok": True, "new": False, "pd": existing[1], "dd": existing[0]}

        os.makedirs(self.pd_dir, exist_ok=True)
        os.makedirs(self.dd_dir, exist_ok=True)
        serial = self.next_serial()
        pd_id, dd_id = f"PD-{serial}", f"DD-{serial}"
        created = now_z()
        probes_json = json.dumps(probes, ensure_ascii=False)

        pd_body = rationale or f"Reasoning for {dd_id} (recorded via the planning cockpit)."
        pd_text = (
            f"---\nid: {pd_id}\npair: {dd_id}\nstatus: draft\n"
            f"source: cockpit:{key}\ncreated: {created}\nprobes: {probes_json}\n---\n\n"
            f"# {pd_id} — reasoning for {dd_id}\n\n{pd_body}\n"
        )
        dd_text = (
            f"---\nid: {dd_id}\npair: {pd_id}\nstatus: draft\n"
            f"source: cockpit:{key}\ncreated: {created}\nprobes: {probes_json}\n---\n\n"
            f"# {title}\n\n{decision}\n\n"
            f"Rationale: {rationale or 'settled via planning cockpit; see ' + pd_id}\n\n"
            f"Done when: {done_when or 'the decision above is realized and verifiable'}\n"
        )
        # PD first, then DD — an orphan PD is benign; an orphan DD bounces at the gate.
        _create_exclusive(os.path.join(self.pd_dir, f"{pd_id}.md"), pd_text)
        _create_exclusive(os.path.join(self.dd_dir, f"{dd_id}.md"), dd_text)
        return {"ok": True, "new": True, "pd": pd_id, "dd": dd_id}

    def settle(self, dd_id):
        if not re.fullmatch(r"DD-\d{3}", dd_id or ""):
            return {"ok": False, "error": f"malformed dd_id: {dd_id!r}"}
        dd_path = os.path.join(self.dd_dir, f"{dd_id}.md")
        if not os.path.isfile(dd_path):
            return {"ok": False, "error": f"{dd_id} not found"}
        fm, _ = self._split(_read(dd_path))
        if fm.get("status") == "settled":
            return {"ok": True, "dd": dd_id}
        _set_status(dd_path, "settled")
        pair = fm.get("pair", "")
        pd_path = os.path.join(self.pd_dir, f"{pair}.md")
        if os.path.isfile(pd_path):
            _set_status(pd_path, "settled")
        return {"ok": True, "dd": dd_id}

    def gate(self):
        if not os.path.isfile(GATE_RUNNER):
            return {"available": False, "error": "gate-runner.py not found"}
        proc = subprocess.run(
            [sys.executable, GATE_RUNNER, DESIGN_INTAKE_GATE, "--project", self.project],
            cwd=FRAMEWORK_ROOT, capture_output=True, text=True)
        verdict = {0: "PASS", 1: "BOUNCE"}.get(proc.returncode, "BLOCK")
        return {"available": True, "verdict": verdict,
                "output": (proc.stdout + proc.stderr).strip()}


# ---------------------------------------------------------------------------
# LLM chat — OpenRouter, with a parsed proposal block.
# ---------------------------------------------------------------------------
def _select_model(req, provider):
    p = PROVIDERS[provider]
    if req.get("deep") and p.get("deep_model"):
        return p["deep_model"]
    model = req.get("model")
    if model and model in p["models"]:
        return model
    # OpenRouter's default (owl-alpha) is not online; upgrade research turns to Sonar.
    if req.get("want_research") and provider == "openrouter" and not model:
        return "perplexity/sonar"
    return p["default"]


PROPOSAL_RE = re.compile(r"```proposal\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_proposal(content):
    m = PROPOSAL_RE.search(content)
    if not m:
        return content.strip(), None
    reply = (content[:m.start()] + content[m.end():]).strip()
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return content.strip(), None
    proposal = {
        "ready": True,
        "title": str(data.get("title", "")).strip(),
        "decision": str(data.get("decision", "")).strip(),
        "rationale": str(data.get("rationale", "")).strip(),
        "done_when": str(data.get("done_when", "")).strip(),
        "probes": [str(p) for p in (data.get("probes") or [])],
    }
    if not proposal["title"] or not proposal["decision"]:
        return content.strip(), None
    return reply, proposal


def _citations(data):
    """Normalize both Perplexity (`citations` URL strings + `search_results`
    dicts) and OpenRouter citation shapes into [{url, title}]."""
    out, seen = [], set()
    for c in data.get("citations", []) or []:
        url = c if isinstance(c, str) else (c.get("url") if isinstance(c, dict) else None)
        if url and url not in seen:
            title = c.get("title", url) if isinstance(c, dict) else url
            out.append({"url": url, "title": title})
            seen.add(url)
    for s in data.get("search_results", []) or []:
        url = s.get("url") if isinstance(s, dict) else None
        if url and url not in seen:
            out.append({"url": url, "title": s.get("title", url)})
            seen.add(url)
    return out


def chat(req):
    provider = req.get("provider")
    if provider not in PROVIDER_ENDPOINTS:
        provider = default_provider()
    endpoint = PROVIDER_ENDPOINTS[provider]
    label = PROVIDERS[provider]["label"]
    key = os.environ.get(endpoint["key_env"])
    if not key:
        return {"ok": False,
                "error": f"{endpoint['key_env']} not set in the server environment"}
    model = _select_model(req, provider)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in req.get("messages", []):
        role = m.get("role")
        if role in ("user", "assistant") and m.get("content"):
            messages.append({"role": role, "content": m["content"]})
    payload = json.dumps({"model": model, "messages": messages}).encode()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/AgenticFrameworks/directive-framework"
        headers["X-Title"] = "Directive Planner Cockpit"
    request = urllib.request.Request(endpoint["url"], data=payload, method="POST",
                                     headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        return {"ok": False, "error": f"{label} {e.code}: {detail}"}
    except (urllib.error.URLError, TimeoutError) as e:
        return {"ok": False, "error": f"{label} unreachable: {e}"}

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return {"ok": False, "error": f"{label} returned no message"}
    reply, proposal = _extract_proposal(content)
    return {
        "ok": True, "reply": reply, "proposal": proposal,
        "probes": proposal["probes"] if proposal else [],
        "citations": _citations(data),
    }


# ---------------------------------------------------------------------------
# Small file helpers (exclusive create + atomic status flip).
# ---------------------------------------------------------------------------
def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _create_exclusive(path, text):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def _set_status(path, status):
    text = _read(path)
    new = re.sub(r"(?m)^status:.*$", f"status: {status}", text, count=1)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# HTTP handler.
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    runtime = None  # set in main()

    def log_message(self, *_):
        pass  # quiet by default

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _static(self, path):
        rel = path.lstrip("/") or "index.html"
        full = os.path.normpath(os.path.join(COCKPIT_DIR, rel))
        if not full.startswith(COCKPIT_DIR) or not os.path.isfile(full):
            self.send_error(404)
            return
        ctype = {
            ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
            ".png": "image/png", ".svg": "image/svg+xml", ".json": "application/json",
        }.get(os.path.splitext(full)[1], "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        r = self.runtime
        if self.path == "/api/board":
            self._json(r.board())
        elif self.path == "/api/config":
            self._json({
                "providers": PROVIDERS,
                "provider_default": default_provider(),
                "is_scratch": r.is_scratch,
                "project": r.project,
                "directives_dir": r.root,
                "counts": r.counts(),
                "search_domains": [],
            })
        elif self.path == "/api/gate":
            self._json(r.gate())
        else:
            self._static(self.path)

    def do_POST(self):
        r = self.runtime
        body = self._body()
        if self.path == "/api/chat":
            self._json(chat(body))
        elif self.path == "/api/accept":
            self._json(r.accept(body))
        elif self.path == "/api/settle":
            self._json(r.settle(body.get("dd_id", "")))
        else:
            self.send_error(404)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default=os.environ.get("DIRECTIVE_PROJECT"),
                    help="project whose _directives/ receives packets "
                         "(default: the framework repo root — a scratch surface)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5000")))
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    is_scratch = args.project is None
    project = args.project or FRAMEWORK_ROOT
    runtime = Runtime(project, is_scratch)
    runtime.ensure()
    Handler.runtime = runtime

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    where = "scratch (repo root)" if is_scratch else runtime.project
    print(f"Directive Planner cockpit → http://{args.host}:{args.port}/")
    print(f"  packets: {runtime.root}  [{where}]")
    print(f"  gate:    {DESIGN_INTAKE_GATE}")
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("  WARNING: OPENROUTER_API_KEY not set — /api/chat will return an error")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
