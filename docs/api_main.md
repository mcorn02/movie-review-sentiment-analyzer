# `api/main.py` — Technical Documentation

---

## 1. Module Overview

`api/main.py` is the **application entrypoint** for the Aspect Sentiment API, a FastAPI-based web service providing domain-agnostic aspect-based sentiment analysis with batch processing capabilities and business report generation.

This module is responsible for:

- **Constructing and configuring the `FastAPI` application instance** that is served by an ASGI server (e.g., `uvicorn`).
- **Managing application lifespan** — specifically, initializing the database before the app begins serving requests.
- **Registering CORS middleware** to allow cross-origin requests from known React development server origins.
- **Mounting all API routers** under a unified `/api` prefix, creating a clean separation between API routes and other content.
- **Serving the compiled frontend SPA** (Single-Page Application) in production environments, including a catch-all fallback route for client-side routing.
- **Exposing a health-check endpoint** for uptime monitoring and load-balancer probes.

Within the broader system architecture, this file sits at the **top of the Python package hierarchy** and is the sole module referenced by the ASGI server. It composes together database initialization (`api.db`), route handlers (`api.routes.*`), and static file serving into a single deployable unit.

---

## 2. Key Components

### Constants

---

#### `FRONTEND_DIST`

```python
FRONTEND_DIST: Path = Path(__file__).resolve().parent.parent / "frontend" / "dist"
```

**What it does:** Resolves the absolute filesystem path to the compiled frontend distribution directory. The path is computed relative to this file's location, navigating two levels up (from `api/`) to the project root, then into `frontend/dist/`.

**Side effects / dependencies:**
- Evaluated at **module import time**.
- The value of this constant gates whether static file serving is configured — if the directory does not exist (e.g., in development without a frontend build), the SPA serving block is skipped entirely.
- Assumes a monorepo layout: `<project_root>/frontend/dist/`.

---

### Lifespan Context Manager

---

#### `lifespan`

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield
```

**What it does:** Implements the FastAPI [lifespan protocol](https://fastapi.tiangolo.com/advanced/events/). Code before `yield` runs on **startup**; code after `yield` (none here) would run on **shutdown**.

| Parameter | Type | Description |
|-----------|------|-------------|
| `app` | `FastAPI` | The FastAPI application instance (injected by the framework). |

**Returns:** An async context manager (used internally by FastAPI; not called directly by user code).

**Side effects:**
- Calls `init_db()` synchronously during application startup, which is expected to create database tables or perform schema migrations.
- Any exception raised in `init_db()` will prevent the application from starting.

---

### Application Instance

---

#### `app`

```python
app = FastAPI(
    title="Aspect Sentiment API",
    description="Domain-agnostic aspect-based sentiment analysis with batch processing and business reports.",
    version="0.2.0",
    lifespan=lifespan,
)
```

**What it does:** The central `FastAPI` application object. This is the ASGI-callable that `uvicorn` (or any other ASGI server) references directly.

**Configuration:**

| Field | Value |
|-------|-------|
| `title` | `"Aspect Sentiment API"` — appears in auto-generated OpenAPI/Swagger docs |
| `description` | Human-readable summary of the API's purpose |
| `version` | `"0.2.0"` — surfaced in the OpenAPI schema |
| `lifespan` | Bound to the `lifespan` async context manager above |

**Registered middleware (applied in order of registration):**

- **`CORSMiddleware`** — see below.

**Mounted routers (all under `/api` prefix):**

| Router | Prefix | Source |
|--------|--------|--------|
| `analyze_router` | `/api` | `api.routes.analyze` |
| `batch_router` | `/api` | `api.routes.batch` |
| `domains_router` | `/api` | `api.routes.domains` |
| `report_router` | `/api` | `api.routes.report` |

---

### Middleware

---

#### CORS Middleware Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**What it does:** Configures Cross-Origin Resource Sharing to allow the React development server to call the API without browser security blocks.

| Parameter | Value | Notes |
|-----------|-------|-------|
| `allow_origins` | Four localhost variants | Covers Vite's default port (`5173`) and CRA's default port (`3000`) on both `localhost` and `127.0.0.1` |
| `allow_credentials` | `True` | Permits cookies and `Authorization` headers in cross-origin requests |
| `allow_methods` | `["*"]` | All HTTP methods permitted |
| `allow_headers` | `["*"]` | All request headers permitted |

**Behavioral note:** In production, when the frontend is served by the same origin as the API (via the SPA static serving block below), CORS restrictions do not apply and this middleware is effectively a no-op for frontend traffic.

---

### Endpoints

---

#### `health`

```python
@app.get("/api/health", tags=["meta"])
def health() -> dict:
```

**What it does:** Returns a minimal JSON payload confirming the application is running. Useful for container health checks, load balancer probes, and uptime monitoring.

**Parameters:** None.

**Returns:**

```json
{ "status": "ok" }
```

**Tags:** `meta` (groups this endpoint separately in the OpenAPI UI).

**Notes:** This is a synchronous (`def`, not `async def`) endpoint, which FastAPI runs in a thread pool. It has no database interaction and should respond near-instantly.

---

#### `serve_spa`

```python
@app.get("/{full_path:path}")
async def serve_spa(request: Request, full_path: str) -> FileResponse:
    """SPA fallback: serve index.html for any non-API, non-static route."""
```

> **Conditional registration:** This endpoint is **only registered if `FRONTEND_DIST` is a valid directory** at import time. It will not exist in a pure API/development environment without a frontend build present.

**What it does:** Acts as a catch-all route to support client-side routing in the React SPA. Tries to serve an exact file match from the `dist/` directory; falls back to `index.html` for all other paths (allowing the React Router to handle routing client-side).

| Parameter | Type | Description |
|-----------|------|-------------|
| `request` | `Request` | The incoming FastAPI/Starlette request object (available for future use). |
| `full_path` | `str` | The path segment captured by `{full_path:path}`, representing everything after the root `/`. |

**Returns:** A `FileResponse`:
- The exact file at `FRONTEND_DIST / full_path` if it exists on disk.
- `FRONTEND_DIST / "index.html"` otherwise.

**Side effects / dependencies:**
- Performs filesystem existence checks (`Path.is_file()`) on each request for non-asset routes.
- Only active when `frontend/dist/` is present (i.e., after `npm run build` or equivalent).

---

### Static File Mount

```python
app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
```

> **Conditional registration:** Same condition as `serve_spa` — only active when `FRONTEND_DIST` exists.

**What it does:** Mounts the compiled frontend's `assets/` subdirectory (JavaScript bundles, CSS, fonts, images) at `/assets`, allowing the browser to fetch them with proper caching headers via Starlette's `StaticFiles` handler.

**Notes:**
- This mount is registered **before** the `serve_spa` catch-all route, which is important — Starlette/FastAPI evaluates routes in registration order, so `/assets/...` requests are handled by the static file server and never fall through to the SPA handler.

---

## 3. What Changed

This commit represents a significant **feature expansion** from `v0.1.0` to `v0.2.0`. The changes fall into four categories:

---

### 3.1 New Imports

```diff
+import os
+from pathlib import Path
+from fastapi import FastAPI, Request
+from fastapi.middleware.cors import CORSMiddleware
+from fastapi.responses import FileResponse
+from fastapi.staticfiles import StaticFiles
+from api.routes.report import router as report_router
```

- `os` is imported (currently unused in the visible code — likely reserved for future environment variable access or left as a minor oversight).
- `Path` enables robust, cross-platform filesystem path manipulation.
- `Request`, `FileResponse`, `StaticFiles`, and `CORSMiddleware` are all required by the new SPA serving and CORS features.
- `report_router` adds a new route group (`api.routes.report`) to the application.

---

### 3.2 CORS Middleware Added

**Before:** No CORS headers were emitted. Any browser-based request from a different origin would be rejected at the browser level.

**After:** CORS is explicitly configured for four localhost origins. This is a **user-visible functional change** — the React development server can now call the API without `Access-Control-Allow-Origin` errors.

---

### 3.3 All Routers Moved to `/api` Prefix

**Before:**
```python
app.include_router(analyze_router)   # routes at e.g. /analyze
app.include_router(batch_router)     # routes at e.g. /batch
app.include_router(domains_router)   # routes at e.g. /domains
```

**After:**
```python
app.include_router(analyze_router, prefix="/api")  # routes at /api/analyze
app.include_router(batch_router,   prefix="/api")  # routes at /api/batch
app.include_router(domains_router,  prefix="/api")  # routes at /api/domains
app.include_router(report_router,   prefix="/api")  # routes at /api/report (new)
```

**Why it matters:** Prefixing all API routes with `/api` creates a clean namespace separation between API endpoints and static frontend assets. This is **a breaking change** for any existing API consumers — all route URLs have changed.

---

### 3.4 Health Endpoint Moved

**Before:** `GET /health`

**After:** `GET /api/health`

This is consistent with the `/api` prefix migration and is **a breaking change** for any health-check configuration pointing to the old URL.

---

### 3.5 `report_router` Added

A new router (`api.routes.report`) is now included, adding business report generation functionality to the API. This is a net-new capability introduced in `v0.2.0`.

---

### 3.6 Frontend SPA Serving Added

**Before:** The application served no static files and had no fallback routes.

**After:** When `frontend/dist/` exists on disk, the application:
1. Mounts `/assets` as a static file directory.
2. Registers a `/{full_path:path}` catch-all that serves real files or falls back to `index.html`.

**Why it matters:** This enables **production deployment as a single process** — one `uvicorn` instance serves both the API and the React frontend, eliminating the need for a separate web server (e.g., Nginx) to serve the frontend in production.

---

### 3.7 Version Bump

```diff
-    version="0.1.0",
+    version="0.2.0",
```

Reflects the extent of functional changes introduced in this commit. Surfaced in the OpenAPI schema at `/docs` and `/openapi.json`.

---

## 4. Dependencies & Integration

### Internal Imports (what this module consumes)

| Import | Source | Purpose |
|--------|--------|---------|
| `init_db` | `api.db` | Initializes the database schema on application startup |
| `analyze_router` | `api.routes.analyze` | Handles single-text sentiment analysis requests |
| `batch_router` | `api.routes.batch` | Handles batch sentiment analysis jobs |
| `domains_router` | `api.routes.domains` | Manages domain definitions/configurations |
| `report_router` | `api.routes.report` | Generates business-level sentiment reports (added in this commit) |

### External / Third-Party Imports

| Library | Usage |
|---------|-------|
| `fastapi` | Core web framework — `FastAPI`, `Request` |
| `fastapi.middleware.cors` | `CORSMiddleware` for cross-origin request handling |
| `fastapi.responses` | `FileResponse` for serving static files |
| `fastapi.staticfiles` | `StaticFiles` for mounting asset directories |
| `pathlib` (stdlib) | `Path` for cross-platform filesystem path resolution |
| `contextlib` (stdlib) | `asynccontextmanager` for lifespan management |
| `os` (stdlib) | Imported but not actively used in current code |

### What Depends on This Module

| Consumer | How it uses `api/main.py` |
|----------|--------------------------|
| **ASGI server** (`uvicorn`) | References `api.main:app` directly as the ASGI callable. Entry command: `uvicorn api.main:app --reload` |
| **Frontend (React SPA)** | All API calls target routes registered in this module; static serving is also configured here |
| **Health monitoring / load balancers** | Polls `GET /api/health` |
| **OpenAPI clients / consumers** | Schema generated from `app` instance reflects all routers and metadata defined here |

### Filesystem Dependencies

| Path | Required | Purpose |
|------|----------|---------|
| `<project_root>/frontend/dist/` | Optional | Enables SPA static file serving when present |
| `<project_root>/frontend/dist/assets/` | Optional | Mounted at `/assets` for JS/CSS bundles |
| `<project_root>/frontend/dist/index.html` | Optional | Served as SPA fallback for unmatched routes |

---

`FUNCTIONAL_CHANGE: YES`
