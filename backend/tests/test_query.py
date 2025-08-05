from tests.utils import *
from tests.constants import *

from pathlib import Path
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from router.file_api import getPathOfImageFile, BASE_DIR
from router.sqlite_api import delete_image, inesrt_or_update_image


def test_query_images(client: TestClient, session: Session):

    def query(text: str, use_text_embed: bool, use_bm25: bool, use_joint_embed: bool):
        assert use_text_embed or use_bm25 or use_joint_embed, "At least one of the query methods must be used"
        response = client.get("/api/query", params={
            "text": text,
            "use_text_embed": use_text_embed,
            "use_bm25": use_bm25,
            "use_joint_embed": use_joint_embed
        })
        
        data = sorted(response.json(), key=lambda x: x['distance'], reverse=True) 
        assert response.status_code == 200
        assert len(data) >= 2 # at least two result should be returned
        assert text in data[0]["filename"] and text in data[1]["filename"]

    inesrt_or_update_image(PATH_HUSKY_IMAGE, session)
    inesrt_or_update_image(PATH_HUSKY_IMAGE_2, session)
    inesrt_or_update_image(PATH_ROBOT_IMAGE, session)
    inesrt_or_update_image(PATH_ROBOT_IMAGE_2, session)

    wait_before_read_vecdb()

    response = client.get("/image")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 4

    response = client.get("/api/query", params={"text": "husky", "use_text_embed": False, "use_bm25": False, "use_joint_embed": False})
    data = response.json()
    assert response.status_code == 200
    assert len(data) == 0

    query("husky", True, True, True)  
    query("robot", True, True, True) 
    query("husky", True, False, False)
    query("robot", True, False, False)
    query("husky", False, True, False)
    query("robot", False, True, False)
    query("husky", False, False, True)
    query("robot", False, False, True)

def test_query_images_within_folder(client: TestClient, session: Session, tmp_path: Path):

    def query(text: str, path: str):
        response = client.get("/api/query", params={
            "text": text,
            "use_text_embed": True,
            "use_bm25": True,
            "use_joint_embed": True,
            "path": path
        })
        assert response.status_code == 200
        data = sorted(response.json(), key=lambda x: x['distance'], reverse=True) 
        
        return data

    inesrt_or_update_image(PATH_HUSKY_IMAGE, session)
    inesrt_or_update_image(PATH_HUSKY_IMAGE_2, session)
    inesrt_or_update_image(PATH_ROBOT_IMAGE, session)
    inesrt_or_update_image(PATH_ROBOT_IMAGE_2, session)

    wait_before_read_vecdb()

    folder_path = Path(BASE_DIR / SUBFOLDER).resolve()

    assert folder_path.is_dir()
    
    data = query("husky", SUBFOLDER)
    assert len(data) >= 1
    assert "husky" in data[0]["filename"]
    
    for item in data:
        assert item["full_path"].startswith(folder_path.as_posix())


    folder_path = Path(BASE_DIR).resolve()

    assert folder_path.is_dir()
    
    data = query("robot", folder_path.as_posix())
    assert len(data) >= 1
    assert "robot" in data[0]["filename"]
    
    for item in data:
        assert item["full_path"].startswith(folder_path.as_posix())


    # test query never seen dir
    assert tmp_path.is_dir()
    response = client.get("/api/query", 
        params={
            "text": "husky", 
            "use_text_embed": True, "use_bm25": True, "use_joint_embed": True,
            "path": tmp_path.as_posix()
        }
    )

    assert response.status_code == 404

    # test query empty dir

    image_path = getPathOfImageFile(PATH_FLOWER_IMAGE)
    target_image_path = tmp_path / PATH_FLOWER_IMAGE

    copy_file(image_path.parent, target_image_path.parent, image_path.name)

    # insert image and delete it to create directory entry of tmp folder
    inesrt_or_update_image(target_image_path, session)
    delete_image(target_image_path, session)

    wait_before_read_vecdb()

    response = client.get("/api/query", 
        params={
            "text": "husky", 
            "use_text_embed": True, "use_bm25": True, "use_joint_embed": True,
            "path": tmp_path.as_posix()
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0



