from __future__ import annotations

import mimetypes
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from pydantic import BaseModel


class UploadedFile(BaseModel):
    file_id: str
    filename: str
    mime_type: str
    size_bytes: int
    path: str


class FileStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, file_id: str) -> Path | None:
        matches = list(self.root.glob(f"{file_id}_*"))
        if not matches:
            return None
        target = matches[0]
        if not target.is_file():
            return None
        return target

    async def save(self, upload: UploadFile) -> UploadedFile:
        file_id = f"file_{uuid4().hex[:12]}"
        filename = upload.filename or file_id
        target = self.root / f"{file_id}_{filename}"
        data = await upload.read()
        target.write_bytes(data)
        mime_type = upload.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return UploadedFile(
            file_id=file_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            path=str(target),
        )

