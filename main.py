from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry, REGISTRY

from app.core.db.mongodb import connect_to_mongo, close_mongo_connection
from app.api.v1.api import api_router
from app.core.setting import config

# Import Prometheus middleware
from app.core.monitoring.prometheus_middleware import PrometheusMiddleware


# Use lifespan context manager instead of @app.on_event for newer FastAPI versions
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()

app = FastAPI(
    title=config.PROJECT_NAME,
    version="0.1.0",
    openapi_url=f"{config.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# ============================================================================
# CORS Middleware
# ============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="static")

# ============================================================================
# Prometheus Middleware (Add BEFORE routes)
# ============================================================================
app.middleware("http")(PrometheusMiddleware())

# ============================================================================
# Static Files
# ============================================================================
app.mount("/static/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="static")

# ============================================================================
# Metrics Endpoint (Add BEFORE api_router to avoid conflicts)
# ============================================================================
@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint
    This endpoint is scraped by Prometheus to collect metrics
    """
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )

# ============================================================================
# Health Check Endpoint
# ============================================================================
@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring
    """
    return {
        "status": "healthy",
        "service": config.PROJECT_NAME,
        "version": "2.0.0"
    }

# ============================================================================
# API Router
# ============================================================================
app.include_router(api_router, prefix=config.API_V1_STR)

# ============================================================================
# Root Endpoint
# ============================================================================
@app.get("/")
async def root():
    return {
        "message": "Factory Management System API",
        "docs": "/redoc",
        "metrics": "/metrics",
        "health": "/health"
    }