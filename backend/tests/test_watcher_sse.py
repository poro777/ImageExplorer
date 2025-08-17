import asyncio
import json
from typing import List
import pytest
from router.watcher_sse import stop_event_stream
from tests.constants import *
from tests.utils import *

from watcher.watchdogService import *

from router.sqlite_api import delete_image, inesrt_or_update_image
from router.file_api import getPathOfImageFile, BASE_DIR

import httpx

def data_to_json(data: str) -> List[dict]:
    result = []
    if data.strip():
        events = data.split("\n\n")
        for event in events:
            if not event.strip():
                continue
            event_type, _, event_data = event.partition("\n")
            result.append({'event': event_type.split(": ")[1], 
                            'data': json.loads(event_data.split(": ", 1)[1])})
    return result

@pytest.mark.timeout(60)
@pytest.mark.asyncio
async def test_sse(async_client: httpx.AsyncClient):
    ready = asyncio.Event()   # used for coordination

    async def consume_sse():
        ready.set()
        response = await async_client.get("/watcher/sse-test")
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("text/event-stream")
        return data_to_json(response.text)

    async def do_work():
        # make sure works run after SSE is ready
        await ready.wait()
        # sse-test stop automatically after few events

    # Run both concurrently
    events, _ = await asyncio.gather(
        consume_sse(),
        do_work()
    )

    test_data = [{"event": "start_processing", "data": {}},
                {"event": "update", "data": {"path": "D:/user/ImageExplorer/backend/images/flower.jpg"}} ,
                {"event": "delete", "data": {"path": "D:/user/ImageExplorer/backend/images/flower.jpg"}},
                {"event": "update", "data": {"path": "D:/user/ImageExplorer/backend/images/flower.jpg"}},
                {"event": "stop_processing", "data": {}}]
    
    assert events == test_data
    

@pytest.mark.timeout(60)
@pytest.mark.asyncio
async def test_folder_sse(async_client: httpx.AsyncClient, fs_watcher: WatchdogService,):
    ready = asyncio.Event()   # used for coordination

    async def consume_sse():
        ready.set()
        response = await async_client.get("/watcher/sse")
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("text/event-stream")
        return data_to_json(response.text)

    async def do_work():
        await ready.wait()

        test_data = []
        # add base dir
        response = await async_client.post("/watcher/add", params={"path": BASE_DIR.as_posix()}) 
        assert response.status_code == 200
        test_data.append({"event": "create", "data": {"dir": BASE_DIR.as_posix()}})

        response =  await async_client.delete("/watcher/remove", params={"path": BASE_DIR.as_posix(), "delete_images": True})
        assert response.status_code == 200
        test_data.append({"event": "remove", "data": {"dir": BASE_DIR.as_posix()}})

        stop_event_stream()
        return test_data

    # Run both concurrently
    events, test_data = await asyncio.gather(
        consume_sse(),
        do_work()
    )

    assert events == test_data


@pytest.mark.timeout(60)
@pytest.mark.asyncio
async def test_changefile_sse(async_client: httpx.AsyncClient, tmp_images_path: Path, fs_watcher: WatchdogService):
    ready = asyncio.Event()   # used for coordination

    async def consume_sse():
        ready.set()
        response = await async_client.get("/watcher/sse")
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("text/event-stream")
        return data_to_json(response.text)

    async def do_work():
        await ready.wait()

        test_data = []

        test_data.append({"event": "start_processing", "data": {}})

        deleted_file = tmp_images_path / HUSKY_IMAGE
        delete_file(deleted_file)
        test_data.append({"event": "delete", "data": {"path": deleted_file.as_posix()}})
        
        old_file = tmp_images_path / FLOWER_IMAGE
        new_file = tmp_images_path / ("renamed_" + HUSKY_IMAGE)
        rename_file(tmp_images_path, old_file.name, new_file.name)
        test_data.append({"event": "delete", "data": {"path": old_file.as_posix()}})
        test_data.append({"event": "update", "data": {"path": new_file.as_posix()}})

        file = tmp_images_path / ROBOT_IMAGE_2
        copy_file(tmp_images_path / SUBFOLDER, tmp_images_path, ROBOT_IMAGE_2)
        test_data.append({"event": "update", "data": {"path": file.as_posix()}})

        test_data.append({"event": "stop_processing", "data": {}})

        wait_watchdog_done()
        stop_event_stream()
        return test_data

    # linsten tmp_images_path
    response = await async_client.post("/watcher/add", params={"path": tmp_images_path.as_posix()}) 
    assert response.status_code == 200

    events, test_data = await asyncio.gather(
        consume_sse(),
        do_work()
    )

    for event, test_event in zip(events, test_data):
        assert event["event"] == test_event["event"]
        assert event["data"] == test_event["data"]