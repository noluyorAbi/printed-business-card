"""The geometry service.

Vercel cannot carry shapely, trimesh, matplotlib and opencv inside a
serverless function, so the heavy half of Card Studio lives here in a
container and Vercel proxies it. Nothing in this file is reachable from a
browser: every route but /health needs the shared token that only the Vercel
route handlers hold.
"""

import asyncio
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

sys.path.insert(0, str(Path(__file__).resolve().parent))

import render  # noqa: E402
from models import CardSpec, ExportRequest  # noqa: E402

TOKEN = os.environ.get("WORKER_TOKEN", "")
MAX_BODY = 8 * 1024                     # a spec is a few hundred bytes
RENDER_TIMEOUT = float(os.environ.get("RENDER_TIMEOUT", "20"))

# Geometry is CPU bound and releases the GIL only in parts, so requests run on
# a small pool rather than the event loop. One worker per core, minus the one
# serving HTTP.
POOL = ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1))

app = FastAPI(title="Card Studio worker", docs_url=None, redoc_url=None)
bearer = HTTPBearer(auto_error=False)


def authorize(cred: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not TOKEN:
        raise HTTPException(503, "WORKER_TOKEN is not configured")
    if cred is None or cred.credentials != TOKEN:
        raise HTTPException(401, "bad token")


@app.middleware("http")
async def limit_body(request: Request, call_next):
    declared = request.headers.get("content-length")
    if declared and int(declared) > MAX_BODY:
        return JSONResponse({"detail": "spec too large"}, status_code=413)
    return await call_next(request)


async def offload(fn, *args):
    """Run a blocking build with a deadline, so one bad spec cannot wedge us."""
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(loop.run_in_executor(POOL, fn, *args),
                                      RENDER_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "render timed out")


@app.get("/health")
def health():
    return {"ok": True, "styles": len(render.catalog()["styles"])}


@app.get("/styles", dependencies=[Depends(authorize)])
def styles():
    return render.catalog()


@app.post("/render", dependencies=[Depends(authorize)])
async def do_render(spec: CardSpec):
    started = time.perf_counter()
    out = await offload(render.render, spec)
    out["ms"] = round((time.perf_counter() - started) * 1000)
    return out


@app.post("/export", dependencies=[Depends(authorize)])
async def do_export(req: ExportRequest):
    try:
        data, media, filename = await offload(render.export, req.spec, req.format)
    except render.CheckFailed as failed:
        # a card that cannot be printed is not a file worth handing out, and
        # the editor already knows how to render these issues
        raise HTTPException(422, {"detail": "print check failed",
                                  "issues": failed.issues})
    return Response(content=data, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "public, max-age=31536000, immutable",
    })
