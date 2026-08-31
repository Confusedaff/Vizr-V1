# AI Algorithm Visualizer

Turns a natural-language prompt (or a manually-specified algorithm + input)
into a polished, production-quality video visualizing that algorithm — 14
templates spanning arrays, trees, graphs, hashmaps, stacks, linked lists,
and dynamic programming. Full auth, per-user job isolation, S3-compatible
video storage, optional per-render Docker sandboxing, and a web frontend
with live pipeline visibility.

## Why this architecture

The core bet is **schema-driven, deterministic rendering**: an LLM never
writes Manim/Python code and never touches a rendering process directly.
It only ever emits a `Scene` — a Pydantic-validated JSON document built
from a closed vocabulary of ~26 actions (`set_pointer`, `highlight_range`,
`swap`, `visit_node`, `fill_dp_cell`, `push_stack`, ...). A hand-written
compiler (`manim_engine/renderer/compiler.py`) deterministically maps that
JSON to one of 14 hand-written, hand-tested Manim scene classes. This means:

- **No prompt injection / code-execution surface.** There's no code string
  from the LLM to sandbox, escape, or audit — just data, validated by
  Pydantic before it ever reaches a renderer. (The Docker sandbox and AST
  safety validator exist as defense-in-depth on top of this, not because
  the primary path needs them to be safe.)
- **Debuggable by construction.** Every layer (classification, scene
  planning, rendering, quality validation, upload) is a plain function you
  can call in isolation, log, and inspect — end to end, from the debug CLI
  to the production API to the web UI's debug panel.
- **Consistent visual quality.** Every visualization type shares the same
  component library (`manim_engine/components/`), so styling, boundary
  protection, and semantic coloring are enforced in one place.

## What's implemented

| Area | Status |
|---|---|
| 14 algorithm templates | ✅ all render end-to-end, pass frame-quality gates |
| Schema-driven rendering (no LLM code-gen) | ✅ |
| Frame-quality debugging (blank/clipping/contrast/overlap) | ✅ |
| Granular per-stage debug artifacts | ✅ |
| JWT auth, per-user job isolation | ✅ |
| S3/MinIO video storage | ✅ (tested against mocked S3; live MinIO needs a real run) |
| Docker-sandboxed rendering | ✅ (flag construction unit-tested; needs a live Docker host to fully verify) |
| Web frontend (React) | ✅ tested live against the real backend via Playwright |
| Full async stack (FastAPI + Celery + Redis + Postgres) | ✅ |

## Repository layout

```
packages/scene_schema/       The Scene JSON contract (Pydantic models).
                              Closed action vocabulary + semantic bounds
                              checking. Single source of truth: same
                              schema validates LLM output, feeds the LLM's
                              own system prompt, and is the only input the
                              renderer compiler accepts.

manim_engine/
  components/                 Reusable Manim building blocks: ArrayVisualizer,
                               TreeVisualizer, GraphVisualizer, HashMapVisualizer,
                               StackVisualizer, DPTableVisualizer, LinkedListVisualizer,
                               PointerGroup, CodePanel, TitleBar, CaptionBar.
                               All boundary-protection / auto-sizing math lives
                               here (renderer/layout.py).
  templates/                   One Scene subclass per visualization_type (14
                               total): array_traversal, two_sum, two_pointers,
                               binary_search, sliding_window, bubble_sort,
                               merge_sort, quicksort, binary_tree_traversal,
                               graph_bfs_dfs, hashmap_ops, linked_list_reversal,
                               valid_parentheses, dynamic_programming_1d.
  renderer/                    config.py, layout.py, compiler.py,
                               validate_render.py (the quality gate),
                               ast_safety.py (defense-in-depth), sandbox.py +
                               sandbox_entrypoint.py (Docker isolation).
  debug/                       frame_quality.py (pixel + geometric frame
                               inspection), stage_logger.py + manifest.py
                               (granular per-stage debug artifacts).

workers/
  llm/client.py                Multi-provider LLM wrapper (Groq default,
                                Gemini, Anthropic). Per-request user API
                                keys, operator env-var fallback, no shared
                                default — pipeline pauses for manual input
                                if neither is present.
  pipeline/                    classify.py, plan_scene.py, repair.py, render.py,
                                orchestrator.py — plain functions over
                                dataclasses and the filesystem. Zero dependency
                                on FastAPI/Celery/Postgres, so the debug CLI
                                exercises the exact same code as production.
  tasks.py                      Celery task layer: bridges orchestrator results
                                to Postgres job rows, Redis pub/sub events, and
                                the S3/MinIO upload stage.

apps/api/
  auth/                         JWT creation/verification (python-jose), bcrypt
                                 password hashing, FastAPI auth dependencies.
  storage/s3_client.py           S3-compatible (MinIO by default) upload/
                                 presign/delete client.
  models/db.py                   SQLAlchemy models: User, Job (user-scoped),
                                 JobEvent.
  routers/                       auth.py, jobs.py (every route ownership-
                                 checked), debug.py (same, plus path-traversal
                                 guards).
  websocket/gateway.py            Live per-job event streaming, JWT-authenticated
                                 over the query string, ownership-checked before
                                 the socket is accepted.

apps/web/                       React + TypeScript + Vite frontend. A public
                                 landing page (/) with a stylized hero, prompt
                                 bar, and a static per-category showcase
                                 carousel, all routing "Get Started" into
                                 auth. Once signed in (/app), the same prompt
                                 or manual-input job creation, live
                                 pipeline-trace view, video playback with
                                 presigned-URL refresh, and a debug panel
                                 exposing the manifest/quality-report data.

debug_cli/run_pipeline.py      Standalone CLI: run any stage (or the whole
                                pipeline) with zero infrastructure.

tests/                         Schema, frame-quality, AST-safety, layout,
                                sandbox (mocked docker), S3 (mocked via moto),
                                and full end-to-end template-render
                                integration tests (marked `slow`).

infrastructure/docker/         Dockerfile (API/worker), Dockerfile.sandbox
                                (per-render isolation), Dockerfile.web
                                (frontend), init-db.sql.
docker-compose.yml              Full stack: postgres, redis, minio (+ init),
                                api, worker, sandbox-image-builder, web.
```

## Running it

### Fastest path: no infrastructure at all

```bash
pip install -r requirements.txt

python debug_cli/run_pipeline.py validate-scene --scene-file my_scene.json
python debug_cli/run_pipeline.py from-scene --scene-file my_scene.json --job-id demo1
python debug_cli/run_pipeline.py inspect --job-id demo1
cat debug_runs/demo1/manifest.json
```

### Full stack (recommended)

```bash
cp .env.example .env
# edit .env: set JWT_SECRET_KEY (openssl rand -hex 32), optionally GROQ_API_KEY
docker compose up --build
```

This starts Postgres, Redis, MinIO (with bucket auto-created), the sandbox
image build, the API on `:8000`, the worker, and the web frontend on
`:5173`. Open `http://localhost:5173`, sign up, and create a job.

### Auth

```bash
curl -X POST localhost:8000/auth/signup -d '{"email":"you@example.com","password":"..."}' -H 'Content-Type: application/json'
curl -X POST localhost:8000/auth/login/json -d '{"email":"you@example.com","password":"..."}' -H 'Content-Type: application/json'
# -> {"access_token": "...", "token_type": "bearer"}
curl localhost:8000/jobs -H "Authorization: Bearer <token>"
```

Every job, debug endpoint, and WebSocket connection is scoped to the
authenticated user — accessing another user's job returns 404, not 403,
so existence isn't leaked either.

### Getting a free LLM API key (for local development)

The classify and plan-scene stages need an LLM. Three providers are
supported; **Groq is the default** because it's the fastest to set up:

| Provider | Free tier | Setup time | Get a key |
|---|---|---|---|
| **Groq** (default) | Yes, generous, no credit card | ~30 seconds | [console.groq.com/keys](https://console.groq.com/keys) — sign in with Google/GitHub, click "Create API Key" |
| **Gemini** | Yes, no credit card | ~1 minute | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — sign in with a Google account, click "Create API key" |
| Anthropic | No free tier | — | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) |

**Fastest path while developing**: paste your key into `.env` as
`GROQ_API_KEY=gsk_...` (or `GEMINI_API_KEY=...`) before `docker compose up`
— every job then uses it automatically with no per-request key needed.
This is an operator-level fallback meant for your own local development,
not something you'd leave set in a real shared deployment.

**Per-request path** (what end users of a real deployment see): the
frontend's job-creation form has a "LLM provider & API key" section where
anyone can pick Groq/Gemini/Anthropic and paste their own key for that
one request — nothing server-side is required, and the key is only sent
with that job's request, never stored server-side. The frontend also
remembers your choice per-provider in the browser's local storage so you
don't have to re-paste it every time while testing locally.

If neither a per-request key nor an operator fallback is available, the
job pauses at `needs_manual_input` and can be resumed via
`POST /jobs/{id}/manual-scene` with hand-written steps instead of failing
outright.

## Debugging — granular, at every layer

**Every job produces a full audit trail** at `debug_runs/{job_id}/`:
classify/plan_scene/render/validate_render inputs, outputs, and timing;
`manifest.json` (per-stage summary); `pipeline.log` (structured event
stream). The exact same data is available:
- Via the debug CLI: `python debug_cli/run_pipeline.py inspect --job-id X`
- Via HTTP: `GET /debug/jobs/{id}/manifest`, `/quality-report`, `/stages`
- **In the web UI**: every job page has a "Debug details" panel showing
  stage timings and frame-quality results pulled live from the backend,
  and a pipeline-trace view showing exactly which stage failed and why.

**Frame-quality checks** (`manim_engine/debug/frame_quality.py`) gate
whether a render can reach `completed`:
- `blank_frame`, `offscreen_clipping`, `low_contrast_text_regions` — pixel-based
- `overlap_density` — pixel-based, coarse (documented blind spot for thin strokes)
- `mobject_bbox_overlap` — **exact** geometric check on Manim's own
  coordinates; this one found every real layout bug during development

Run it standalone: `python debug_cli/run_pipeline.py check-frames --video path/to/video.mp4`

## Testing

```bash
pytest tests/ -m "not slow"     # fast: schema, frame-quality, AST, layout, sandbox, S3 (~60 tests, <15s)
pytest tests/ -m slow           # slow: full render of all 14 templates (~40s)
pytest tests/                   # everything

cd apps/web && npx tsc --noEmit && npm run build   # frontend typecheck + build
```

## Known limitations (honest scope)

- **Docker sandbox**: flag construction and result-parsing are unit-tested
  (mocked `docker run`), but this development environment has no Docker
  daemon, so a live render through the sandbox hasn't been directly
  observed here. Falls back to subprocess mode automatically if the
  sandbox image isn't available — verify the sandboxed path specifically
  before depending on its isolation guarantees in production.
- **S3/MinIO**: the client is tested thoroughly against a mocked S3
  protocol server (moto), and the pipeline's upload stage has been
  exercised against an intentionally-unreachable endpoint to confirm
  graceful failure — but not against a live MinIO container in this
  environment (no Docker here to run one).
- `overlap_density`'s pixel-statistics approach has a documented blind
  spot for thin strokes — `mobject_bbox_overlap` is authoritative.
- No refresh-token rotation — access tokens expire (30 min default) and
  require re-login; no revocation list.
- No rate limiting on auth endpoints.
- Frontend has no test suite of its own beyond TypeScript's type checker
  and the manual Playwright-driven verification done during development
  (which did catch one real backend routing bug — see git history /
  code comments in `apps/api/routers/jobs.py`).
