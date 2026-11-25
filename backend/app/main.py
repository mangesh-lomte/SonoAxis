import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.app.core.config import settings
from backend.app.db.schema import init_db
from backend.app.api.endpoints import public_router as public_api_router, router as api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize local SQLite database schema and templates
    init_db()
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="SonoAxis 100% Local Speech Recognition and Clinical Ultrasound Reporting Suite",
    lifespan=lifespan
)

# CORS restricted strictly to localhost loopback
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers FIRST so /api/* is prioritized
app.include_router(public_api_router)
app.include_router(api_router)

# Legacy testing interface static directory
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Production React frontend static directory
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
assets_dir = os.path.join(frontend_dist, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# SPA catch-all route for frontend navigation
@app.get("/{full_path:path}")
def serve_spa(full_path: str = ""):
    # Check if a specific file exists in frontend_dist (e.g. favicon.svg, icons.svg)
    if full_path:
        direct_file = os.path.join(frontend_dist, full_path)
        if os.path.isfile(direct_file):
            return FileResponse(direct_file)
    
    # Return React index.html for all client-side routes (/, /reports, /patients, etc.)
    react_index = os.path.join(frontend_dist, "index.html")
    if os.path.exists(react_index):
        return FileResponse(
            react_index,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    return {"message": "Frontend build not found"}
    return {"message": "SonoVoice service running. Frontend dist not built."}
