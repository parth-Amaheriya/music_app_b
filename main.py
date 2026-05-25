import asyncio
from fastapi import FastAPI, BackgroundTasks, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import os
import uuid
from typing import List, Dict, Optional

from yt_music import YouTubeMusic  # We'll update this too

app = FastAPI(title="YouTube Music API", version="2.0")

# CORS - Allow frontend (Vite dev server) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve downloaded files
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

# In-memory task storage (use Redis in production)
tasks: Dict[str, Dict] = {}

class SearchResponse(BaseModel):
    results: List[Dict]

class DownloadResponse(BaseModel):
    task_id: str
    status: str
    message: str

# ===================== ASYNC ENDPOINTS =====================

@app.get("/search", response_model=SearchResponse)
async def search_music(q: str = Query(..., min_length=1), limit: int = 10):
    """Search YouTube Music - Async"""
    try:
        results = await asyncio.to_thread(YouTubeMusic.search, q, limit)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/download", response_model=DownloadResponse)
async def download_music(url: str, background_tasks: BackgroundTasks):
    """Start async background download"""
    if not url or "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(400, detail="Valid YouTube URL is required")
    
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "queued", "title": None, "progress": "0%"}
    
    # Add to background tasks
    background_tasks.add_task(download_background_task, url, task_id)
    
    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Download queued successfully"
    }


@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Check download status"""
    if task_id not in tasks:
        raise HTTPException(404, detail="Task not found")
    return tasks[task_id]


@app.get("/recommendations")
async def get_recommendations(url: str, limit: int = 10):
    """Get recommendations - Async"""
    try:
        recs = await asyncio.to_thread(YouTubeMusic.get_recommendations, url, limit)
        return {"recommendations": recs}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/info")
async def get_video_info(url: str):
    """Get video info - Async"""
    try:
        info = await asyncio.to_thread(YouTubeMusic.get_info, url)
        if "error" in info:
            raise HTTPException(400, detail=info["error"])
        return info
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/download/{filename}")
async def serve_file(filename: str):
    """Serve downloaded file"""
    file_path = DOWNLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, detail="File not found")
    return FileResponse(
        path=file_path,
        media_type="audio/opus",
        filename=filename
    )


# ===================== BACKGROUND TASK =====================

async def download_background_task(url: str, task_id: str):
    """Run download in thread to keep API responsive"""
    tasks[task_id]["status"] = "downloading"
    
    try:
        result = await asyncio.to_thread(YouTubeMusic.download_audio, url, task_id)
        
        tasks[task_id].update({
            "status": result.get("status", "completed"),
            "title": result.get("title"),
            "filename": result.get("filename"),
            "download_url": result.get("download_url"),
            "error": result.get("error")
        })
    except Exception as e:
        tasks[task_id].update({
            "status": "failed",
            "error": str(e)
        })


# ===================== ROOT =====================

@app.get("/")
async def root():
    return {
        "message": "🎵 Async YouTube Music API is Running!",
        "docs": "/docs",
        "endpoints": {
            "search": "GET /search?q=perfect+by+ed+sheeran&limit=8",
            "download": "POST /download?url=...",
            "status": "GET /task/{task_id}",
            "info": "GET /info?url=..."
        }
    }