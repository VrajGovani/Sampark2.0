import sys
import traceback
from pathlib import Path

# Add project root directory to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from app.main import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    error_trace = traceback.format_exc()
    print("Vercel Startup Error:\n", error_trace)
    app = FastAPI()
    
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    def catch_all(path: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "status": "Vercel Startup Error",
                "error": str(e),
                "traceback": error_trace.splitlines()
            }
        )
