
from fastapi import APIRouter
from pathlib import Path
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect

from router import watcher_api
from database import database


router = APIRouter()

@router.websocket("/ws/watcher/add")
async def ws_add_path_to_listener(websocket: WebSocket, path: str):
    await websocket.accept()
    session = next(database.get_session())

    async def progress_cb(current, total):
        print(f"Processing {current}/{total} files")
        await websocket.send_json({"processing": f"{current}/{total}"})

    try:
        images = await watcher_api.process_folder(Path(path), session, progress_cb=progress_cb)
        await websocket.send_json({"done": images})
    except WebSocketDisconnect:
        print("WebSocket disconnected during processing")
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        raise e
    finally:
        await websocket.close()
