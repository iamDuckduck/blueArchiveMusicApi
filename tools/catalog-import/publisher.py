"""Publish one reviewed release through the backend's idempotent import API."""

import json
import mimetypes
from pathlib import Path

import requests

from store import find_track, now


class Publisher:
    def __init__(self, store, backend_url, api_key):
        self.store = store
        self.backend_url = backend_url.rstrip("/")
        self.api_key = api_key

    def publish(self):
        state = self.store.view()
        self._validate(state)
        album = state["album"]
        identity = album["id"]
        headers = {"X-Admin-Api-Key": self.api_key}
        cover = album["cover"]["files"]
        metadata = {
            "title": album["fields"]["title"],
            "category": album["fields"]["category"],
            "releaseDate": album["fields"]["release_date"] or None,
            "description": album["fields"]["notes"],
        }
        with self._open(cover["original"]["path"]) as original, \
                self._open(cover["400"]["path"]) as cover400, \
                self._open(cover["800"]["path"]) as cover800:
            response = requests.put(
                f"{self.backend_url}/admin/catalog-import/kivo/albums/{identity}",
                headers=headers,
                files={
                    "metadata": (None, json.dumps(metadata, ensure_ascii=False), "application/json"),
                    "coverOriginal": (Path(original.name).name, original, mimetypes.guess_type(original.name)[0]),
                    "cover400": (Path(cover400.name).name, cover400, "image/jpeg"),
                    "cover800": (Path(cover800.name).name, cover800, "image/jpeg"),
                }, timeout=120, allow_redirects=False)
        album_result = self._result(response)
        self.store.update(lambda saved: saved["publication"].update(
            status="running", album=album_result, message="Album published; publishing tracks…", updated_at=now()))

        for track in state["tracks"]:
            if not track["publish_selected"] or not track["included"] or track["source_id"] is None:
                continue
            fields = track["fields"]
            track_metadata = {
                "title": fields["title"], "disc": fields["disc"],
                "position": fields["position"], "kind": fields["kind"],
                "displayOrder": fields["display_order"],
                "description": fields["notes"], "artists": fields["group"],
                "composers": fields["composer"],
                "performers": [{"character": item["character"], "voiceActor": item["voice_actor"]}
                               for item in fields["performers"]],
            }
            with self._open(track["media"]["path"]) as audio:
                response = requests.put(
                    f"{self.backend_url}/admin/catalog-import/kivo/albums/{identity}/tracks/{track['source_id']}",
                    headers=headers,
                    files={"metadata": (None, json.dumps(track_metadata, ensure_ascii=False), "application/json"),
                           "audio": (Path(audio.name).name, audio, mimetypes.guess_type(audio.name)[0])},
                    timeout=180, allow_redirects=False)
            result = self._result(response)
            self.store.update(lambda saved, track_id=track["id"], value=result:
                              saved["publication"].setdefault("tracks", {}).update({track_id: value}))

        final = self.store.update(lambda saved: saved["publication"].update(
            status="ready", message="Published successfully. Safe to publish again.", updated_at=now()))
        return final["publication"]

    def _open(self, relative):
        target = (self.store.directory / relative).resolve()
        if not target.is_relative_to(self.store.directory) or not target.is_file():
            raise ValueError("A prepared media file is missing. Prepare the release again.")
        return target.open("rb")

    def _validate(self, state):
        if not self.api_key:
            raise ValueError("Set CATALOG_IMPORT_API_KEY before publishing.")
        if state["album"]["decision"] != "included":
            raise ValueError("Include the album before publishing.")
        files = state["album"]["cover"].get("files", {})
        if state["album"]["cover"].get("status") != "ready" or not {"original", "400", "800"} <= files.keys():
            raise ValueError("Prepare the album cover before publishing.")
        tracks = [t for t in state["tracks"] if t["publish_selected"] and t["included"] and t["source_id"] is not None]
        if not tracks:
            raise ValueError("Select at least one prepared music track for publication.")
        if any(t["media"].get("status") != "ready" or not t["media"].get("path") for t in tracks):
            raise ValueError("Every track selected for publication must be prepared. Leave missing tracks unselected to publish available music.")

    def _result(self, response):
        if not 200 <= response.status_code < 300:
            raise ValueError(f"Backend rejected publication ({response.status_code}): {response.text[:500]}")
        return response.json()
