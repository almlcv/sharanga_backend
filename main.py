from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.db.mongodb import connect_to_mongo, close_mongo_connection
from app.api.v1.api import api_router
from app.core.setting import config


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

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="static")

# Include the main API router
app.include_router(api_router, prefix=config.API_V1_STR)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Factory Management System API",
        "docs": "/redoc"
    }