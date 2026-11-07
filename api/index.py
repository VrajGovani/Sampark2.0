import sys
import traceback
from pathlib import Path
from fastapi import Request
from fastapi.responses import JSONResponse

# Add project root directory to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from app.main import app

    @app.middleware("http")
    async def vercel_handler_middleware(request: Request, call_next):
        try:
            # Fix path rewrites on Vercel
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
        except Exception as exc:
            err_trace = traceback.format_exc()
            print("RUNTIME ERROR IN REQUEST:\n", err_trace, file=sys.stderr)
            return JSONResponse(
                status_code=500,
                content={
                    "status": "RUNTIME_ERROR",
                    "error": str(exc),
                    "traceback": err_trace.splitlines()
                }
            )

except Exception as e:
    from fastapi import FastAPI

    app = FastAPI()
    startup_trace = traceback.format_exc()
    print("STARTUP IMPORT ERROR:\n", startup_trace, file=sys.stderr)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def catch_all(path: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "status": "STARTUP_IMPORT_ERROR",
                "error": str(e),
                "traceback": startup_trace.splitlines()
            }
        )

    @app.get("/")
    def root():
        return JSONResponse(
            status_code=500,
            content={
                "status": "STARTUP_IMPORT_ERROR",
                "error": str(e),
                "traceback": startup_trace.splitlines()
            }
        )
