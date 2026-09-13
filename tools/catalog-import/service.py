"""One background preparation job; the browser stays responsive."""

import threading

import media
import sources
from store import find_track, now


class ReviewService:
    def __init__(self, store):
        self.store = store
        self.job_lock = threading.Lock()
        self.thread = None

    def start(self, action):
        if action not in {"fetch", "prepare", "gamekee"}:
            raise ValueError("Unknown action.")
        if not self.job_lock.acquire(blocking=False):
            raise ValueError("A preparation task is already running.")
        if action == "prepare" and self.store.read()["album"]["decision"] != "included":
            self.job_lock.release()
            raise ValueError("Include the album before preparing files.")
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
            else:
                self.prepare()
            self.store.update(lambda s: s["job"].update(running=False, message="Finished. Review the results and any source or preparation warnings.", finished_at=now()))
        except Exception as error:
            self.store.update(lambda s: s["job"].update(running=False, message=f"Task stopped: {error}. Retry to continue.", finished_at=now()))
        finally:
            self.job_lock.release()

    def fetch_tracks(self, only_missing=False):
        for track in self.store.read()["tracks"]:
            if track["source_id"] is None or (only_missing and track["source"]):
                continue
            track_id = track["source_id"]
            self.message(f"Reading Kivo track {track_id}…")
            try:
                data = sources.fetch_kivo(track_id)

                def save(state):
                    row = find_track(state, track_id)
                    row.update(source=data, source_status="ready", source_error="", source_fetched_at=now())
                    row["suggestions"].update(sources.suggestions_from_kivo(data))
                    if track_id == 255 and data.get("album"):
                        state["album"]["suggestions"]["title"] = data["album"]

                self.store.update(save)
            except Exception as error:
                reason = str(error)
                self.store.update(lambda s: find_track(s, track_id).update(source_status="failed", source_error=reason))

    def fetch_gamekee(self, force=False):
        previous = self.store.read()["gamekee"]
        if previous["status"] != "pending" and not force:
            return
        self.message("Checking the matching GameKee album…")
        result = sources.fetch_gamekee()
        saved_text = previous.get("text") or previous.get("cached_text")
        if result["status"] == "failed" and saved_text:
            result["cached_text"] = saved_text
        self.store.update(lambda s: s.update(gamekee=result))

    def prepare(self):
        self.fetch_tracks(only_missing=True)
        self.fetch_gamekee()
        state = self.store.read()
        cover_url = next((t["source"].get("cover") for t in state["tracks"] if t["source"] and t["source"].get("cover")), "")
        previous_cover = state["album"]["cover"]
        self.message("Preparing the original cover and smaller display copies…")
        self.store.update(lambda s: s["album"]["cover"].update(status="running", error=""))
        try:
            if not cover_url:
                raise ValueError("No cover URL is available. Refresh source information and try again.")
            cover = media.prepare_cover(self.store.directory, cover_url, previous_cover)
            self.store.update(lambda s: s["album"].update(cover=cover))
        except Exception as error:
            reason = str(error)
            self.store.update(lambda s: s["album"]["cover"].update(status="failed", error=reason))

        for track in self.store.read()["tracks"]:
            if not track["included"] or track["source_id"] is None:
                continue
            track_id = track["id"]
            previous = track["media"]
            self.message(f"Preparing audio and reading file credits for track {track_id}…")
            self.store.update(lambda s: find_track(s, track_id)["media"].update(status="running", error=""))
            try:
                source = track["source"]
                if not source or not source.get("file"):
                    raise ValueError("No audio URL is available. The track is kept here for a later retry.")
                prepared = media.prepare_audio(self.store.directory, track_id, source["file"], previous)

                def save(state):
                    row = find_track(state, track_id)
                    row["media"] = prepared
                    row["tags"] = prepared["tags"]
                    row["suggestions"].update(sources.suggestions_from_tags(prepared["tags"]))

                self.store.update(save)
            except Exception as error:
                reason = str(error)
                self.store.update(lambda s: find_track(s, track_id)["media"].update(status="failed", error=reason))
