from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
import os

from .routes import search, auth, dashboard
from .database import engine, Base

app = FastAPI(
    title="Sampark 2.0 - Vehicle Contact Directory",
    description="Connect with vehicle owners instantly via plate lookup",
    version="1.0.0"
)

# Create database tables automatically on startup
@app.on_event("startup")
def on_startup():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print("Startup DB check:", e)

# Health check route for instant diagnostic
@app.get("/health")
def health_check():
    return {"status": "ok", "app": "Sampark 2.0", "message": "Service is healthy"}

# Exception handler for login redirects
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 303 and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=303)
    if exc.status_code == 401:
        return RedirectResponse(url="/login?error=Please+sign+in+first.", status_code=303)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# Catch-all exception handler to display actionable tracebacks
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    import sys
    tb = traceback.format_exc()
    print("GLOBAL UNHANDLED EXCEPTION:\n", tb, file=sys.stderr)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(
        status_code=500,
        content=f"<html><body style='font-family:monospace;padding:24px;background:#0f172a;color:#f8fafc;'>"
                f"<h2 style='color:#f87171'>🚨 500 Internal Server Error</h2>"
                f"<p style='color:#fbbf24'><b>Error:</b> {str(exc)}</p>"
                f"<pre style='background:#1e293b;padding:16px;border-radius:12px;overflow:auto;color:#4ade80'>{tb}</pre>"
                f"</body></html>"
    )

# Include Routers
app.include_router(search.router)
app.include_router(auth.router)
app.include_router(dashboard.router)

if __name__ == "__main__":
    import uvicorn
    Base.metadata.create_all(bind=engine)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
