from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
import os

from .database import engine, Base
from .routes import search, auth, dashboard

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safe table verification on startup
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Startup notice: {e}")
    yield

app = FastAPI(
    title="Sampark 2.0 - Vehicle Contact Directory",
    description="Connect with vehicle owners instantly via plate lookup",
    version="1.0.0",
    lifespan=lifespan
)

# Health check route for instant diagnostic
@app.get("/health")
def health_check():
    return {"status": "ok", "app": "Sampark 2.0", "message": "Serverless function is healthy"}

# Exception handler for login redirects
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 303 and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=303)
    return RedirectResponse(url="/login?error=Session+expired.+Please+login.", status_code=303)

# Include Routers
app.include_router(search.router)
app.include_router(auth.router)
app.include_router(dashboard.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
