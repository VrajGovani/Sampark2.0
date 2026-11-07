import sys
import traceback
from pathlib import Path

# Add project root directory to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ASGI Middleware to correct rewritten paths on Vercel
class VercelPathFixMiddleware:
    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            # Vercel sends the original requested URL path in x-matched-path
            matched_path = headers.get(b"x-matched-path")
            if matched_path:
                scope["path"] = matched_path.decode("utf-8")
            else:
                raw_path = scope.get("path", "")
                for prefix in ("/api/index.py", "/api/index"):
                    if raw_path.startswith(prefix):
                        rest = raw_path[len(prefix):]
                        scope["path"] = rest if rest else "/"
                        break
        await self.asgi_app(scope, receive, send)

try:
    from app.main import app as fastapi_app
    app = VercelPathFixMiddleware(fastapi_app)
except Exception as e:
    STARTUP_ERROR = str(e)
    STARTUP_TRACE = traceback.format_exc()
    print("Vercel Startup Error:\n", STARTUP_TRACE)

    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    err_app = FastAPI()

    ERROR_HTML = f"""
    <html><body style="font-family:monospace;padding:2em;background:#1e1e1e;color:#f8f8f8">
    <h2 style="color:#ff6b6b">🚨 Sampark Startup Error on Vercel</h2>
    <p><b>Error:</b> <span style="color:#ffd93d">{STARTUP_ERROR}</span></p>
    <h3>Full Traceback:</h3>
    <pre style="background:#111;padding:1em;overflow:auto;color:#a8ff78">{"<br>".join(STARTUP_TRACE.splitlines())}</pre>
    <hr><p style="color:#aaa">Tip: Check Vercel → Project → Settings → Environment Variables for DATABASE_URL</p>
    </body></html>
    """

    @err_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def catch_all(path: str = ""):
        return HTMLResponse(content=ERROR_HTML, status_code=500)

    app = VercelPathFixMiddleware(err_app)
