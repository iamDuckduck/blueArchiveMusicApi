"""One background preparation job; the browser stays responsive."""

import threading

import media
import sources
from store import find_track, now, propose_fields
from publisher import PublicationConflict


class ReviewService:
    def __init__(self, store, publisher=None):
        self.store = store
        self.publisher = publisher
        self.job_lock = threading.Lock()
        self.thread = None

    def start(self, action):
        if action not in {"fetch", "prepare", "refresh", "gamekee", "publish", "published"}:
            raise ValueError("Unknown action.")
        if not self.job_lock.acquire(blocking=False):
            raise ValueError("A preparation task is already running.")
        if action in {"prepare", "refresh"} and self.store.read()["album"]["decision"] != "included":
            self.job_lock.release()
            raise ValueError("Include the album before preparing files.")
        if action in {"publish", "published"} and self.publisher is None:
            self.job_lock.release()
            raise ValueError("Publication is not configured. Start the tool with a backend URL and API key.")
        self.store.update(lambda s: s.update(job={"running": True, "action": action, "message": "Starting…", "started_at": now()}))
        self.thread = threading.Thread(target=self._run, args=(action,), daemon=True)
        self.thread.start()

    def message(self, message):
        self.store.update(lambda s: s["job"].update(message=message))

    def _run(self, action):
        try:
            if action == "fetch":
                self.fetch_tracks()
                self.fetch_gamekee()
            elif action == "gamekee":
                self.fetch_gamekee(force=True)
            elif action == "publish":
                self.publisher.publish()
            elif action == "published":
                self.publisher.observe_published()
            else:
                self.prepare(force=action == "refresh")
            self.store.update(lambda s: s["job"].update(running=False, message="Finished. Review the results and any source or preparation warnings.", finished_at=now()))
        except Exception as error:
            if action == "publish":
                conflict = isinstance(error, PublicationConflict)
                self.store.update(lambda s: s["publication"].update(
                    status="conflict" if conflict else "failed",
                    message=str(error) if conflict else f"Publication stopped: {error}. Safe to retry."))
            self.store.update(lambda s: s["job"].update(running=False, message=f"Task stopped: {error}. Retry to continue.", finished_at=now()))
        finally:
            self.job_lock.release()

    def fetch_tracks(self, only_missing=False):
        for track in self.store.read()["tracks"]:
            if track["source_id"] is None or (only_missing and track["source"]):
                continue
            if only_missing and not track["included"]:
                continue
            track_id = track["source_id"]
            self.message(f"Reading Kivo track {track_id}…")
            try:
                data = sources.fetch_kivo(track_id)

                def save(state):
                    row = find_track(state, track_id)
                    if row["source"] and row["source"] != data:
                        row.setdefault("source_history", []).append({"fetched_at":row.get("source_fetched_at"), "raw":row["source"]})
                        row["publish_selected"] = False
                        propose_fields(row, "kivo", sources.suggestions_from_kivo(data), sources.suggestions_from_kivo(row["source"]))
                    elif not row["source"]:
                        row["suggestions"].update(sources.suggestions_from_kivo(data))
                    row.update(source=data, source_status="ready", source_error="", source_fetched_at=now())
                    if row.get("pending_index"):
                        row["index"] = row.pop("pending_index")
                        row.pop("index_warning", None)
                    # The selected official release is an operator decision, not a detail-record label.

                self.store.update(save)
            except Exception as error:
                reason = str(error)
                self.store.update(lambda s: find_track(s, track_id).update(source_status="failed", source_error=reason))

    def fetch_gamekee(self, force=False):
        state = self.store.view()
        previous = state["gamekee"]
        page_url = state["album"]["fields"]["gamekee_url"]
        if not force and previous["status"] != "pending" and previous.get("url") == page_url:
            return
        self.message("Checking the matching GameKee album…")
        result = sources.fetch_gamekee(page_url)
        result["url"] = page_url
        saved_text = (previous.get("text") or previous.get("cached_text")) if previous.get("url", page_url) == page_url else None
        if result["status"] == "failed" and saved_text:
            result["cached_text"] = saved_text
            result["cached_checked_at"] = previous.get("cached_checked_at") or previous.get("checked_at")
            if previous.get("evidence") or previous.get("cached_evidence"):
                result["cached_evidence"] = previous.get("evidence") or previous.get("cached_evidence")
        self.store.update(lambda s: s.update(gamekee=result))

    def prepare(self, force=False):
        self.fetch_tracks(only_missing=not force)
        self.fetch_gamekee()
        state = self.store.read()
        cover_url = next((t["source"].get("cover") for t in state["tracks"]
                          if t["included"] and t["source_id"] is not None
                          and t["source"] and t["source"].get("cover")), "")
        previous_cover = state["album"]["cover"]
        self.message("Preparing the original cover and smaller display copies…")
        self.store.update(lambda s: s["album"].update(cover={"status":"running", "previous":previous_cover}))
        try:
            if not cover_url:
                raise ValueError("No cover URL is available. Refresh source information and try again.")
            cover = media.prepare_cover(self.store.directory, cover_url, previous_cover, **({"force":True} if force else {}))
            def save_cover(state):
                old_hashes = {key: value.get("sha256") for key, value in previous_cover.get("files", {}).items()}
                new_hashes = {key: value.get("sha256") for key, value in cover.get("files", {}).items()}
                if previous_cover.get("status") == "ready" and old_hashes != new_hashes:
                    state["album"].setdefault("cover_history", []).append(previous_cover)
                    for row in state["tracks"]:
                        row["publish_selected"] = False
                state["album"]["cover"] = cover
            self.store.update(save_cover)
        except Exception as error:
            reason = str(error)
            self.store.update(lambda s: s["album"].update(cover=previous_cover | {
                "status":"ready" if previous_cover.get("status") == "ready" else "failed", "error":reason}))

        for track in self.store.read()["tracks"]:
            if not track["included"] or track["source_id"] is None:
                continue
            track_id = track["id"]
            previous = track["media"]
            self.message(f"Preparing audio and reading file credits for track {track_id}…")
            self.store.update(lambda s: find_track(s, track_id).update(media={"status":"running", "previous":previous}))
            try:
                source = track["source"]
                if not source or not source.get("file"):
                    raise ValueError("No audio URL is available. The track is kept here for a later retry.")
                prepared = media.prepare_audio(self.store.directory, track_id, source["file"], previous, **({"force":True} if force else {}))

                def save(state):
                    row = find_track(state, track_id)
                    if previous.get("status") == "ready" and previous.get("sha256") != prepared.get("sha256"):
                        row.setdefault("media_history", []).append(previous)
                        row["publish_selected"] = False
                    row["media"] = prepared
                    if previous.get("status") == "ready":
                        propose_fields(row, "tags", sources.suggestions_from_tags(prepared["tags"]), sources.suggestions_from_tags(row["tags"]))
                    else:
                        row["suggestions"].update(sources.suggestions_from_tags(prepared["tags"]))
                    row["tags"] = prepared["tags"]

                self.store.update(save)
            except Exception as error:
                reason = str(error)
                self.store.update(lambda s: find_track(s, track_id).update(media=previous | {
                    "status":"ready" if previous.get("status") == "ready" else "failed", "error":reason}))
