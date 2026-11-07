import sys
import traceback
from pathlib import Path

# Add project root directory to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STARTUP_ERROR = None
STARTUP_TRACE = None

try:
    from app.main import app
except Exception as e:
    STARTUP_ERROR = str(e)
    STARTUP_TRACE = traceback.format_exc()
    print("Vercel Startup Error:\n", STARTUP_TRACE)

    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse

    app = FastAPI()

    ERROR_HTML = f"""
    <html><body style="font-family:monospace;padding:2em;background:#1e1e1e;color:#f8f8f8">
    <h2 style="color:#ff6b6b">🚨 Sampark Startup Error on Vercel</h2>
    <p><b>Error:</b> <span style="color:#ffd93d">{STARTUP_ERROR}</span></p>
    <h3>Full Traceback:</h3>
    <pre style="background:#111;padding:1em;overflow:auto;color:#a8ff78">{"<br>".join(STARTUP_TRACE.splitlines())}</pre>
    <hr><p style="color:#aaa">Tip: Check Vercel → Project → Settings → Environment Variables for DATABASE_URL</p>
    </body></html>
    """

    @app.get("/")
    def root_error():
        return HTMLResponse(content=ERROR_HTML, status_code=500)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def catch_all(path: str = ""):
        return HTMLResponse(content=ERROR_HTML, status_code=500)
