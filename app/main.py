from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import os

from .database import engine, Base
from .routes import search, auth, dashboard

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="Sampark 2.0 - Vehicle Contact Directory",
    description="Connect with vehicle owners instantly via plate lookup",
    version="1.0.0",
    lifespan=lifespan
)

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
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

