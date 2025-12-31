from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

# Add parent directory to path to import config
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import settings
from app.utils.database import engine, Base

# Import all models to ensure they are registered with SQLAlchemy
from app.models import heart_rate

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Heart Rate Monitoring API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # Use configured origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Import routes after app creation to avoid circular imports
from app.routes import face_routes, rppg_routes, websocket_routes

# Include API routes
app.include_router(face_routes.router, prefix="/api/face", tags=["Face Recognition"])
app.include_router(rppg_routes.router, prefix="/api/rppg", tags=["rPPG"])
app.include_router(websocket_routes.router, prefix="/ws", tags=["WebSocket"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Heart Rate Monitoring API is running"}

# Mount static files for frontend - after API routes to ensure they are accessible
# Use absolute path to ensure it works regardless of where the server is run from
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
frontend_dir = os.path.join(project_root, "frontend")
print(f"Mounting frontend from: {frontend_dir}")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
