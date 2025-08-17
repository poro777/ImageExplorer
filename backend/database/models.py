from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from sqlalchemy import UniqueConstraint

class Directory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    path: str = Field(index=True, unique=True)  # full absolute path
    last_modified: Optional[datetime] = Field(default=None)
    is_watching: bool = Field(default=False)

    # relationship to images
    images: List["Image"] = Relationship(back_populates="directory")


class Image(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("directory_id", "filename", name="uix_directory_filename"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    full_path : str = Field(default=None, unique=True)
    width: Optional[int] = None
    height: Optional[int] = None
    thumbnail_path: Optional[str] = Field(default=None, unique=True)

    directory_id: int = Field(foreign_key="directory.id")
    directory: Optional[Directory] = Relationship(back_populates="images")

    last_modified: Optional[datetime] = Field(default=None)
    file_size: Optional[int] = Field(default=None)  # in bytes