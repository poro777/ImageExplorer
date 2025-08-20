import asyncio
import json
import threading
from fastapi import APIRouter, HTTPException, Request
from pathlib import Path
from fastapi import Depends
from fastapi.responses import StreamingResponse
from fastapi import WebSocket, WebSocketDisconnect

router = APIRouter(
    prefix="/watcher",
    tags=["watcher"],
)
# Store each client as an asyncio.Queue
subscribers: list[asyncio.Queue] = []

lock = threading.Lock()
processCount = 0

def stop_event_stream():
    """Stop the event stream by clearing the subscribers list."""
    global subscribers
    for queue in subscribers:
        queue.put_nowait(None)  # Signal to stop the stream
    print("Subscribers have been cleared.", len(subscribers))

def broadcast_start_processing_event():
    """Start processing a folder and notify all subscribers."""
    with lock:
        global processCount
        processCount += 1

    broadcast_event("start_processing")

def broadcast_stop_processing_event():
    """Stop processing a folder and notify all subscribers."""
    with lock:
        global processCount
        processCount -= 1
    if processCount == 0:
        broadcast_event("stop_processing")

def broadcast_event(event: str, data: dict = None):
    """Send event to all connected clients."""
    asyncio.run(_broadcast_event(event, data))

async def _broadcast_event(event: str, data: dict = None):
    """Send event to all connected clients."""
    item = {
        "event": event,
        "data": data if data is not None else {}
    }
    disconnected = []
    for queue in subscribers:
        try:
            await queue.put(item)
        except asyncio.CancelledError:
            disconnected.append(queue)
    # Remove broken queues
    for queue in disconnected:
        if queue in subscribers:
            print("Client disconnected, removing queue.")
            subscribers.remove(queue)

async def sse_event_stream(client_queue: asyncio.Queue):
    """Yields events from a single client's queue."""
    try:
        while True:
            event = await client_queue.get()
            if event is None:  # Stop signal
                break
            yield f"event: {event['event']}\n"
            yield f"data: {json.dumps(event['data'])}\n\n"
            client_queue.task_done()
    except asyncio.CancelledError:
        pass
    finally:
        print("Client disconnected, removing queue.")
        if client_queue in subscribers:
            subscribers.remove(client_queue)

@router.get("/sse-test")
async def sse_test(request: Request):
    """Handle a new SSE client connection."""
    async def test(client_queue):
        """Yields events from a single client's queue."""
        try:
            while True:
                event = await client_queue.get()
                if event is None:  # Stop signal
                    break
                yield f"event: {event['event']}\n"
                yield f"data: {json.dumps(event['data'])}\n\n"
                client_queue.task_done()
                await asyncio.sleep(1)  # Simulate some delay
        except asyncio.CancelledError:
            pass
        finally:
            print("Client disconnected. (test)")

    client_queue = asyncio.Queue()
    client_queue.put_nowait({"event": "start_processing", "data": {}})
    client_queue.put_nowait({"event": "update", "data": {"path": "D:/user/ImageExplorer/backend/images/flower.jpg"}})
    client_queue.put_nowait({"event": "delete", "data": {"path": "D:/user/ImageExplorer/backend/images/flower.jpg"}})
    client_queue.put_nowait({"event": "update", "data": {"path": "D:/user/ImageExplorer/backend/images/flower.jpg"}})
    client_queue.put_nowait({"event": "stop_processing", "data": {}})

    client_queue.put_nowait(None)  # Stop signal for the test
    return StreamingResponse(test(client_queue),
                             media_type="text/event-stream")

@router.get("/sse")
async def sse(request: Request):
    """Handle a new SSE client connection."""
    client_queue = asyncio.Queue()
    subscribers.append(client_queue)

    return StreamingResponse(sse_event_stream(client_queue),
                             media_type="text/event-stream")