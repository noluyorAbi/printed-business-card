"""Vercel entrypoint for the geometry worker.

It is the same FastAPI app the container runs. Vercel's Python runtime serves
an ASGI application exported as `app`, and the rewrite in `vercel.json` sends
every path here, so the routes are unchanged: /health, /styles, /render,
/export.

Why this file sits in the repository root rather than in `worker/`: a Vercel
function only ever bundles its project's root directory. With `worker/` as the
root, `build_card.py` was simply not there, and the function failed on import.
The root is the smallest tree that contains both.

And why this fits on Vercel at all, since the plan first said it would not:
the heavy half of the dependency list is test-only. opencv decodes QR codes in
the test suite and inside `check_printability(decode=True)`, which the service
never calls, and zxing-cpp only reads a barcode in CI. What remains is 133 MB
installed, inside the 250 MB a Python function may occupy, and matplotlib
brings its own DejaVu fonts so there is nothing to install for those either.

What is left is a cold start of roughly five seconds while shapely, trimesh
and matplotlib import. The editor caches on the spec hash and the route in
front of this holds the last few hundred answers, so it is paid rarely. The
container in `worker/` remains the option when that is not good enough; see
DEPLOY.md.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from worker.app import app  # noqa: E402

__all__ = ["app"]
