"""Publish one reviewed release through the backend's idempotent import API."""

import json
import hashlib
import mimetypes
from datetime import date
from pathlib import Path

import requests

from store import find_track, now
from sources import absolute_url


class PublicationConflict(ValueError):
    pass


def needs_media_refresh(track):
    source_url = (track.get("source") or {}).get("file")
    return bool(source_url and track["media"].get("status") == "ready"
                and absolute_url(source_url) != track["media"].get("source_url"))


class Publisher:
    def __init__(self, store, backend_url, api_key):
        self.store = store
        self.backend_url = backend_url.rstrip("/")
        self.api_key = api_key

    def publish(self):
        state = self.store.view()
        records = ["album"] + [track["id"] for track in state["tracks"]
                               if track["publish_selected"] and track["included"] and track["source_id"] is not None]
        self.store.update(lambda saved: saved["publication"].update(attempt={
            "destination": self.backend_url,
            "records": [{"record": record, "status": "not_sent"} for record in records],
        }))
        try:
            return self._publish(state)
        except Exception as error:
            def stop_attempt(saved):
                for item in saved["publication"]["attempt"]["records"]:
                    if item["status"] == "sending":
                        item["status"] = "conflict" if isinstance(error, PublicationConflict) else "failed"
            self.store.update(stop_attempt)
            raise

    def _publish(self, state):
        self._validate(state)
        album = state["album"]
        identity = album["id"]
        headers = self._headers("album")
        cover = album["cover"]["files"]
        metadata = {
            "title": album["fields"]["title"],
            "category": album["fields"]["category"],
            "releaseDate": album["fields"]["release_date"] or None,
            "description": album["fields"]["notes"],
        }
        self._attempt_status("album", "sending")
        with self._open(cover["original"]) as original, \
                self._open(cover["400"]) as cover400, \
                self._open(cover["800"]) as cover800:
            response = requests.put(
                f"{self.backend_url}/admin/catalog-import/kivo/albums/{identity}",
                headers=headers,
                files={
                    "metadata": (None, json.dumps(metadata, ensure_ascii=False), "application/json"),
                    "coverOriginal": (Path(original.name).name, original, mimetypes.guess_type(original.name)[0]),
                    "cover400": (Path(cover400.name).name, cover400, "image/jpeg"),
                    "cover800": (Path(cover800.name).name, cover800, "image/jpeg"),
                }, timeout=120, allow_redirects=False)
        album_result = self._result(response, "album")
        self._save_receipt("album", album_result)
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
            self._attempt_status(track["id"], "sending")
            with self._open(track["media"]) as audio:
                response = requests.put(
                    f"{self.backend_url}/admin/catalog-import/kivo/albums/{identity}/tracks/{track['source_id']}",
                    headers=self._headers(track["id"]),
                    files={"metadata": (None, json.dumps(track_metadata, ensure_ascii=False), "application/json"),
                           "audio": (Path(audio.name).name, audio, mimetypes.guess_type(audio.name)[0])},
                    timeout=180, allow_redirects=False)
            result = self._result(response, track["id"])
            self._save_receipt(track["id"], result)
            self.store.update(lambda saved, track_id=track["id"], value=result:
                              saved["publication"].setdefault("tracks", {}).update({track_id: value}))

        final = self.store.update(lambda saved: saved["publication"].update(
            status="ready", message="Published successfully. Safe to publish again.", updated_at=now()))
        return final["publication"]

    def _open(self, item):
        target = (self.store.directory / item["path"]).resolve()
        if not target.is_relative_to((self.store.directory / "media").resolve()) or not target.is_file():
            raise ValueError("A prepared media file is missing. Prepare the release again.")
        stream = target.open("rb")
        try:
            if hashlib.file_digest(stream, "sha256").hexdigest() != item.get("sha256"):
                raise ValueError("Prepared media changed or has no validation hash. Prepare it again before publication.")
            stream.seek(0)
            return stream
        except BaseException:
            stream.close()
            raise

    def _destination(self, state):
        return state["publication"].setdefault("destinations", {}).setdefault(self.backend_url, {"receipts":{}, "observed":{}})

    def _headers(self, record):
        saved = self._destination(self.store.read())["receipts"].get(record, {})
        headers = {"X-Admin-Api-Key": self.api_key}
        if saved.get("revision"):
            headers["X-Catalog-Revision"] = saved["revision"]
        return headers

    def _save_receipt(self, record, result):
        def save(saved):
            destination = self._destination(saved)
            destination["receipts"][record] = result
            if destination.get("conflict") == record:
                destination.pop("conflict")
            item = next(item for item in saved["publication"]["attempt"]["records"] if item["record"] == record)
            item["status"] = "unchanged" if result.get("status") == "unchanged" else "saved"
        self.store.update(save)

    def _attempt_status(self, record, status):
        def save(saved):
            item = next(item for item in saved["publication"]["attempt"]["records"] if item["record"] == record)
            item["status"] = status
        self.store.update(save)

    def observe_published(self):
        state = self.store.read()
        base = f"{self.backend_url}/admin/catalog-import/kivo/albums/{state['album']['id']}"
        records = [("album", base)] + [(t["id"], base + f"/tracks/{t['source_id']}") for t in state["tracks"] if t["source_id"] is not None]
        for record, url in records:
            response = requests.get(url, headers={"X-Admin-Api-Key":self.api_key}, timeout=30, allow_redirects=False)
            if response.status_code != 200:
                raise ValueError(f"Cannot read published {record} ({response.status_code}). Saved baselines were not changed.")
            current = response.json()
            self._check_snapshot(current)
            self.store.update(lambda saved, record=record, current=current:
                              self._destination(saved)["observed"].update({record:current | {"observed_at":now()}}))

    def accept_baseline(self, record, revision):
        def save(state):
            destination = self._destination(state)
            current = destination["observed"].get(record)
            if current is None or current.get("revision") != revision:
                raise ValueError("The displayed published snapshot changed. Compare the current snapshot first.")
            destination["receipts"][record] = {key:current.get(key) for key in ["albumId", "songId", "revision"]}
            if record == "album":
                for row in state["tracks"]:
                    row["publish_selected"] = False
            else:
                find_track(state, record)["publish_selected"] = False
            if destination.get("conflict") == record:
                destination.pop("conflict")
            state["publication"].update(status="pending", message="Baseline accepted. Your draft and prepared media are unchanged. Review and select tracks before publishing.")
        self.store.update(save)

    def _validate(self, state):
        if not self.api_key:
            raise ValueError("Set CATALOG_IMPORT_API_KEY before publishing.")
        if state["album"]["decision"] != "included":
            raise ValueError("Include the album before publishing.")
        album_fields = state["album"]["fields"]
        for field in ["title", "category"]:
            if not album_fields[field].strip() or len(album_fields[field]) > 255:
                raise ValueError(f"Enter an album/collection {field} between 1 and 255 characters before publishing.")
        if album_fields["release_date"]:
            try:
                parsed = date.fromisoformat(album_fields["release_date"])
                if parsed.isoformat() != album_fields["release_date"]:
                    raise ValueError()
            except ValueError:
                raise ValueError("Use a valid YYYY-MM-DD release date, or leave it blank if unknown.")
        files = state["album"]["cover"].get("files", {})
        if state["album"]["cover"].get("status") != "ready" or not {"original", "400", "800"} <= files.keys():
            raise ValueError("Prepare the album cover before publishing.")
        tracks = [t for t in state["tracks"] if t["publish_selected"] and t["included"] and t["source_id"] is not None]
        if not tracks:
            raise ValueError("Select at least one prepared music track for publication.")
        for track in tracks:
            if not track["fields"]["title"].strip() or len(track["fields"]["title"]) > 255:
                raise ValueError(f"Enter a title between 1 and 255 characters for selected track {track['id']} before publishing.")
            if track["fields"]["kind"] == "drama":
                raise ValueError("Spoken drama cannot be published as music.")
        if any(t.get("pending_index") for t in tracks):
            raise ValueError("The source index changed. Reload Kivo details and review the selected tracks before publishing.")
        if any(needs_media_refresh(t) for t in tracks):
            raise ValueError("A selected track's source audio URL changed. Prepare it again before publishing; the previous validated file is retained.")
        if any(t["media"].get("status") != "ready" or not t["media"].get("path") for t in tracks):
            raise ValueError("Every track selected for publication must be prepared. Leave missing tracks unselected to publish available music.")
        if any(t.get("pending_suggestions") for t in tracks):
            raise ValueError("Compare incoming source suggestions for selected tracks: use them or keep the reviewed values before publishing.")

    def _result(self, response, record):
        if response.status_code == 409:
            current = response.json().get("current")
            if isinstance(current, dict):
                self._check_snapshot(current)
                def save(state):
                    destination = self._destination(state)
                    destination["observed"][record] = current | {"observed_at":now()}
                    destination["conflict"] = record
                self.store.update(save)
            raise PublicationConflict(f"Published {record} changed. Compare the shown catalog snapshot, then explicitly accept a baseline before publishing your draft. This record was not overwritten; earlier successful records from this attempt remain published.")
        if not 200 <= response.status_code < 300:
            raise ValueError(f"Backend rejected publication ({response.status_code}): {response.text[:500]}")
        result = response.json()
        revision = result.get("revision") if isinstance(result, dict) else None
        if not isinstance(revision, str) or len(revision) != 64 or any(c not in "0123456789abcdef" for c in revision):
            raise ValueError("Backend returned no valid publication revision. Update the backend before publishing changes; identical retries remain safe.")
        return result

    @staticmethod
    def _check_snapshot(current):
        if (not isinstance(current, dict) or type(current.get("exists")) is not bool
                or not isinstance(current.get("metadata"), dict) or not isinstance(current.get("media"), dict)):
            raise ValueError("Backend did not return a catalog snapshot. Update the backend before reconciling.")
        revision = current.get("revision")
        if current["exists"]:
            if not isinstance(revision, str) or len(revision) != 64 or any(c not in "0123456789abcdef" for c in revision):
                raise ValueError("Published snapshot has no valid revision; its baseline was not accepted.")
        elif revision is not None:
            raise ValueError("Missing catalog records cannot have a publication revision.")
