from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, UploadFile, status

SAFE_EXTENSIONS = {
    ".pdf", ".docx", ".tex", ".zip", ".xlsx", ".xls", ".csv", ".tsv",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".md", ".txt", ".py",
    ".js", ".ts", ".tsx", ".jsx", ".cpp", ".cc", ".c", ".h", ".hpp",
    ".java", ".json", ".yaml", ".yml", ".toml", ".rs", ".go", ".ipynb",
}


def safe_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SAFE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension: {ext or '(none)'}",
        )
    return ext


def normalize_filename(filename: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name).strip("._")
    return clean[:180] or "material"


async def persist_upload(
    upload: UploadFile,
    destination: Path,
    max_bytes: int,
) -> tuple[int, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".part")
    digest = hashlib.sha256()
    size = 0
    try:
        with temp.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="Uploaded file exceeds configured size limit")
                digest.update(chunk)
                handle.write(chunk)
        temp.replace(destination)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return size, digest.hexdigest()
