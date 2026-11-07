import sys
import traceback
from pathlib import Path
from fastapi import Request

# Add project root directory to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from app.main import app

    @app.middleware("http")
    async def fix_vercel_path(request: Request, call_next):
        matched = request.headers.get("x-matched-path")
        if matched:
            request.scope["path"] = matched
        else:
            raw = request.scope.get("path", "")
            for prefix in ("/api/index.py", "/api/index"):
                if raw.startswith(prefix):
                    sub = raw[len(prefix):]
                    request.scope["path"] = sub if sub else "/"
                    break
        return await call_next(request)

except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI()
    err_trace = traceback.format_exc()

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def catch_all(path: str = ""):
        return HTMLResponse(
            content=f"<html><body style='font-family:monospace;padding:2em;background:#1e1e1e;color:#fff'>"
                    f"<h2 style='color:#ff6b6b'>🚨 Vercel Startup Error</h2>"
                    f"<pre style='background:#111;padding:1em;color:#a8ff78'>{err_trace}</pre>"
                    f"</body></html>",
            status_code=500
        )
