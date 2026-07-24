# Directive Planner — Cockpit surface

An interactive, research-grounded **planning front door** for the Directive Framework.
You converse to converge on scope, then accept a settled decision — which is written as a
**gate-passing `PD` ⇄ `DD` packet pair** into a project's `_directives/`, verifiable by the
canon `design-intake` gate straight from the UI.

The cockpit is a thin frontend (a static Vite build) over a small **backend** that owns all
runtime writes and shells out to the real framework tools. The frontend cannot function on
its own — it depends on the backend's `/api/*` endpoints.

## Contents

| Path | Purpose |
|---|---|
| `index.html` | App entry (Vite build), served same-origin by the backend |
| `assets/index-*.js` | Compiled application bundle (API base repointed to same-origin `/api`) |
| `assets/index-*.css` | Compiled styles |
| `server/app.py` | The backend: static server + six `/api/*` endpoints (stdlib only) |

The frontend is a **built artifact** (upstream source lives outside this repo). The backend
under `server/` is first-class source maintained here.

## Run it

```bash
# from the repo root — serves UI + API on one origin
OPENROUTER_API_KEY=... python3 cockpit/server/app.py [--project DIR] [--port 5000]
# then open http://localhost:5000/
```

- `--project DIR` — the project whose `_directives/` receives packets. Omit it to use the
  **repo root as a scratch surface** (`is_scratch: true`); point it at a real consuming
  project for actual planning work.
- `OPENROUTER_API_KEY` — required only for `/api/chat`. Per the model-provider policy the
  backend routes through OpenRouter (default model `owl-alpha`; `perplexity/sonar` for
  research turns, `perplexity/sonar-reasoning` for deep probes). The board / accept / settle
  / gate flow works without it. The provider/model set is defined in one place —
  `PROVIDERS` in `server/app.py`.

## API surface (frontend ⇄ backend contract)

| Endpoint | Method | Role |
|---|---|---|
| `/api/config` | GET | providers/models, project info, PD/DD counts |
| `/api/board` | GET | the planning board: cursor phase + PD/DD packets |
| `/api/chat` | POST | converse-to-converge loop (OpenRouter); returns a `proposal` when a decision is ready |
| `/api/accept` | POST | write a ready proposal as a paired `PD`⇄`DD` (idempotent by content hash) |
| `/api/settle` | POST | flip a `DD` (and its `PD`) from `draft` → `settled` |
| `/api/gate` | GET | run `tools/gate-runner.py gates/design-intake.md`; returns the real verdict |

Accepted packets conform to the canon `PD-TEMPLATE.md` / `DD-TEMPLATE.md` contracts
(`id`, `pair`, `status`, `created`, shared serial), so `design-intake` passes. `/api/gate`
runs the actual gate-runner — the cockpit reports PASS/BOUNCE/BLOCK, never a simulation.

## Where it fits

The cockpit sits at the **front** of the five-phase pipeline
(**Planning → Design → Validation → Execution → Review**). It only produces Planning-phase
artifacts (`PD`/`DD`); every downstream gate, lifecycle, and executor contract is unchanged.
See `planning-directives/PLANNING-SPEC.md` for the packet contracts and `gates/design-intake.md`
for the gate the exported packets satisfy.
