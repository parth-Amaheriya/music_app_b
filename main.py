import asyncio
from fastapi import FastAPI, BackgroundTasks, Query, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import os
import uuid
from typing import List, Dict

from yt_music import YouTubeMusic

app = FastAPI(title="YouTube Music API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve downloaded files
DOWNLOAD_DIR = Path("downloads")
app.mount("/downloads", StaticFiles(directory="downloads"), name="downloads")

# In-memory task storage
tasks: Dict[str, Dict] = {}

class SearchResponse(BaseModel):
    results: List[Dict]

class DownloadResponse(BaseModel):
    task_id: str
    status: str
    message: str

# ===================== ENDPOINTS =====================

@app.get("/search", response_model=SearchResponse)
async def search_music(q: str = Query(..., min_length=1), limit: int = 10):
    results = await asyncio.to_thread(YouTubeMusic.search, q, limit)
    return {"results": results}


@app.post("/download", response_model=DownloadResponse)
async def download_music(url: str, background_tasks: BackgroundTasks):
    if not url:
        raise HTTPException(400, detail="URL is required")
    
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "queued", "title": None}
    
    background_tasks.add_task(download_background_task, url, task_id)
    
    return {
        "task_id": task_id,
        "status": "queued",
        "message": "Download started in background"
    }


@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(404, detail="Task not found")
    return tasks[task_id]


@app.get("/tasks")
async def list_tasks():
    return {
        "tasks": [
            {"task_id": task_id, **task_data}
            for task_id, task_data in tasks.items()
        ]
    }


@app.get("/info")
async def get_video_info(url: str):
    info = await asyncio.to_thread(YouTubeMusic.get_info, url)
    if "error" in info:
        raise HTTPException(400, detail=info["error"])
    return info


@app.get("/recommendations")
async def get_recommendations(url: str, limit: int = 10):
    recs = await asyncio.to_thread(YouTubeMusic.get_recommendations, url, limit)
    return {"recommendations": recs}


@app.get("/library")
async def list_library_files():
    files = []
    if DOWNLOAD_DIR.exists():
        for file_path in sorted(DOWNLOAD_DIR.glob("*.opus"), key=lambda path: path.stat().st_mtime, reverse=True):
            stat = file_path.stat()
            files.append(
                {
                    "filename": file_path.name,
                    "title": file_path.stem.rsplit("_", 1)[0],
                    "download_url": f"/download/{file_path.name}",
                    "size_bytes": stat.st_size,
                    "modified_at": stat.st_mtime,
                }
            )

    return {"tracks": files}


@app.get("/download/{filename}")
async def serve_file(filename: str):
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
    tasks[task_id]["status"] = "downloading"
    try:
        result = await asyncio.to_thread(YouTubeMusic.download_audio, url, task_id)
        tasks[task_id].update(result)
    except Exception as e:
        tasks[task_id].update({"status": "failed", "error": str(e)})


@app.get("/")
async def root():
    return {
        "message": "🎵 Async YouTube Music API is Running!",
        "docs": "/docs"
    }