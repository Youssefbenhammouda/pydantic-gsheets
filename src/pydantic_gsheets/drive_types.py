# src/pydantic_gsheets/drive_types.py
from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field
from googleapiclient.discovery import Resource
from googleapiclient.http import MediaIoBaseDownload

# ------------------------
# Drive URL / ID utilities
# ------------------------

_DRIVE_PATTERNS = [
    re.compile(r"https?://drive\.google\.com/file/d/([^/]+)/?"),
    re.compile(r"https?://drive\.google\.com/open\?id=([a-zA-Z0-9_-]{10,})"),
    re.compile(r"https?://drive\.google\.com/uc\?id=([a-zA-Z0-9_-]{10,})"),
    re.compile(r"(?:\?|&)id=([a-zA-Z0-9_-]{10,})"),
]

def extract_drive_file_id(s: str | None) -> Optional[str]:
    if not s:
        return None
    for pat in _DRIVE_PATTERNS:
        m = pat.search(s)
        if m:
            return m.group(1)
    return None


# ---------------
# Public type API
# ---------------

class DriveFile(BaseModel):
    """
    Pydantic type representing a Google Drive-backed file reference found in a sheet cell.
    - url: original URL or IMAGE() URL
    - file_id: extracted Drive file ID (if any)
    - local_path: where it was downloaded (if downloaded)
    - meta: optional file metadata (mimeType, name) from Drive
    """
    url: Optional[str] = None
    file_id: Optional[str] = None
    local_path: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def parse_from_cell(cls, cell_value: Any) -> "DriveFile | None":
        if cell_value is None:
            return None
        v = str(cell_value).strip()
        # Support =IMAGE("...") formulas by extracting the first quoted argument
        if v.upper().startswith("=IMAGE("):
            import re
            m = re.search(r'\"(.*?)\"', v)
            v = m.group(1) if m else v
        fid = extract_drive_file_id(v)
        return cls(url=v, file_id=fid)

    # Convenience method — figures out how to save the file locally
    def ensure_downloaded(
        self,
        drive: Any,
        *,
        dest_dir: str = "downloads",
        filename_template: str = "{name}",
        export_mime: Optional[str] = None,
        overwrite: bool = False,
        row_number: Optional[int] = None,
        field_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Download/export the Drive file to disk and set local_path.
        - If export_mime is provided, uses files.export (for Google Docs/Slides/Drawings).
        - Otherwise uses files.get_media (binary files like PNG/JPG/PDF).
        The filename can use keys: name, id, ext, row, field.
        """
        if self.local_path and os.path.exists(self.local_path) and not overwrite:
            return self.local_path

        fid = self.file_id or extract_drive_file_id(self.url or "")
        if not fid:
            return None

        # Fetch file metadata for naming and decision making
        meta = drive.files().get(fileId=fid, fields="id,name,mimeType").execute()
        self.meta = meta
        basename = meta.get("name", fid)
        mime = meta.get("mimeType", "")

        # Pick extension
        ext = ""
        if export_mime:
            # Map a few common export mimes to extensions
            ext_map = {
                "image/png": "png",
                "image/jpeg": "jpg",
                "application/pdf": "pdf",
                "text/plain": "txt",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
            }
            ext = ext_map.get(export_mime, "")
        else:
            # If it's already a binary (image/*, application/octet-stream, etc), try using original name's extension
            if "." in basename:
                ext = basename.rsplit(".", 1)[1]
            else:
                # Fallback common image
                if mime.startswith("image/"):
                    ext = mime.split("/", 1)[1]

        # Build final filename
        safe_name = basename if "." in basename else (basename + (("." + ext) if ext else ""))
        fn = filename_template.format(
            name=safe_name,
            id=fid,
            ext=ext,
            row=(row_number or ""),
            field=(field_name or ""),
        )

        os.makedirs(dest_dir, exist_ok=True)
        out_path = os.path.join(dest_dir, fn)

        if os.path.exists(out_path) and not overwrite:
            self.local_path = out_path
            return out_path

        # Download
        if export_mime:
            req = drive.files().export_media(fileId=fid, mimeType=export_mime)
        else:
            req = drive.files().get_media(fileId=fid)

        with open(out_path, "wb") as fh:
            downloader = MediaIoBaseDownload(fh, req)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        self.local_path = out_path
        return out_path


# ------------------
# Column annotation
# ------------------

@dataclass
class GSDrive:
    """
    Column-level options for DriveFile fields.
    - predownload: download at read time if Drive service is available
    - dest_dir: directory to save files
    - filename_template: "{name}", or e.g. "{row}_{field}_{id}.{ext}"
    - export_mime: if set, use files.export with this MIME (for Google Docs/Slides/Drawings)
    - overwrite: re-download if file already exists
    """
    predownload: bool = False
    dest_dir: str = "downloads"
    filename_template: str = "{name}"
    export_mime: Optional[str] = None
    overwrite: bool = False
