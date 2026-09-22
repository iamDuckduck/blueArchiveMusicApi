"""Local files only: download, full audio decode and cover derivatives."""

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageOps

from sources import HEADERS, kivo_media_url


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url, target, limit):
    url = kivo_media_url(url)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".part")
    try:
        with requests.get(url, headers=HEADERS, timeout=(10, 40), stream=True, allow_redirects=False) as response:
            if 300 <= response.status_code < 400:
                raise ValueError("The file URL redirected. Refresh and review the source URL before retrying.")
            response.raise_for_status()
            total = 0
            with temporary.open("wb") as stream:
                for chunk in response.iter_content(128 * 1024):
                    total += len(chunk)
                    if total > limit:
                        raise ValueError("The download exceeded this tool's file size limit.")
                    stream.write(chunk)
        if total == 0:
            raise ValueError("Downloaded file is empty.")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def binary(name):
    result = shutil.which(name)
    if not result:
        raise ValueError(f"{name} was not found. Install FFmpeg and add its bin folder to PATH, then retry.")
    return result


def inspect_audio(path):
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    probe = subprocess.run([binary("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                           capture_output=True, timeout=30, creationflags=creation_flags)
    if probe.returncode:
        raise ValueError("Audio inspection failed: " + probe.stderr.decode("utf-8", errors="replace")[:500])
    info = json.loads(probe.stdout)
    audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    duration = float(info.get("format", {}).get("duration", 0))
    if not audio or duration <= 0:
        raise ValueError("The downloaded file has no usable audio stream or duration.")
    decoded = subprocess.run([binary("ffmpeg"), "-nostdin", "-v", "error", "-xerror", "-i", str(path), "-map", "0:a:0", "-f", "null", "-"],
                             capture_output=True, timeout=120, creationflags=creation_flags)
    if decoded.returncode:
        raise ValueError("Full audio validation failed: " + decoded.stderr.decode("utf-8", errors="replace")[:500])
    tags = {}
    for source in (audio.get("tags", {}), info.get("format", {}).get("tags", {})):
        tags.update({k.lower(): str(v) for k, v in source.items()})
    return {"duration": duration, "codec": audio.get("codec_name"), "tags": tags, "sha256": digest(path), "bytes": Path(path).stat().st_size}


def prepare_audio(root, track_id, source_url, previous, force=False):
    url = kivo_media_url(source_url)
    root = Path(root)
    if not force and previous.get("status") == "ready" and previous.get("source_url") == url:
        cached = root / previous["path"]
        if cached.is_file() and digest(cached) == previous.get("sha256"):
            return previous
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in {".mp3", ".ogg", ".wav", ".m4a", ".flac"}:
        raise ValueError("Unrecognized audio extension. Inspect the source manually.")
    directory = root / "media" / str(track_id)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=directory) as temporary:
        incoming = Path(temporary) / ("audio" + suffix)
        download(url, incoming, limit=150 * 1024 * 1024)
        info = inspect_audio(incoming)
        if previous.get("sha256") == info["sha256"] and previous.get("path"):
            old_file = root / previous["path"]
            if old_file.is_file() and digest(old_file) == info["sha256"]:
                return previous | {"status":"ready", "source_url":url, "error":""}
        relative = Path("media") / str(track_id) / ("audio-" + info["sha256"][:24] + suffix)
        target = root / relative
        incoming.replace(target)
    return info | {"status": "ready", "path": relative.as_posix(), "source_url": url}


def resize_cover(original, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with Image.open(original) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        outputs = {}
        for size in (400, 800):
            resized = image.copy()
            resized.thumbnail((size, size), Image.Resampling.LANCZOS)
            output = destination / f"cover-{size}.jpg"
            temporary = output.with_suffix(".part")
            resized.save(temporary, format="JPEG", quality=88, optimize=True)
            temporary.replace(output)
            outputs[str(size)] = {"path": output, "width": resized.width, "height": resized.height}
    return outputs


def prepare_cover(root, source_url, previous, force=False):
    root = Path(root)
    url = kivo_media_url(source_url)
    if not force and previous.get("status") == "ready" and previous.get("source_url") == url:
        files = previous.get("files", {})
        if files and all((root / file["path"]).is_file() and digest(root / file["path"]) == file["sha256"] for file in files.values()):
            return previous
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("Unrecognized cover extension.")
    directory = root / "media" / "cover"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-", dir=directory) as temporary:
        original = Path(temporary) / ("original" + suffix)
        download(url, original, limit=30 * 1024 * 1024)
        outputs = resize_cover(original, original.parent)
        outputs["original"] = {"path": original}
        # Validate and generate every variant before changing the saved review's paths.
        for size, item in outputs.items():
            item["sha256"] = digest(item["path"])
            old = previous.get("files", {}).get(size, {})
            if old.get("sha256") == item["sha256"] and old.get("path") and (root / old["path"]).is_file() and digest(root / old["path"]) == item["sha256"]:
                item["path"] = old["path"]
            else:
                target = directory / (size + "-" + item["sha256"][:24] + item["path"].suffix)
                item["path"].replace(target)
                item["path"] = target.relative_to(root).as_posix()
    return {"status": "ready", "source_url": url, "files": outputs}
