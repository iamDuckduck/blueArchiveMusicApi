"""A single saved album review. Source suggestions never overwrite operator edits."""

import json
import sqlite3
import threading
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from credits import CREDIT_FIELDS, credit_entries

TRACK_FIELDS = {"title", "position", "disc", "display_order", "kind", "group", "performers", "composer", "notes"}


def validate_fields(values, allowed):
    if not isinstance(values, dict) or values.keys() - allowed:
        raise ValueError("Unknown review field.")
    for key, value in values.items():
        if key in CREDIT_FIELDS:
            values[key] = credit_entries(key, value)
        elif key == "display_order":
            if type(value) is not int or not 1 <= value <= 999999:
                raise ValueError("Display order must be between 1 and 999999; leave official numbering blank if unknown.")
        elif key in {"position", "disc"}:
            if value is not None and (type(value) is not int or not 1 <= value <= 999):
                raise ValueError("Track and disc numbers must be between 1 and 999, or blank.")
        elif not isinstance(value, str) or len(value) > 20000:
            raise ValueError("Review fields must be text, up to 20,000 characters.")
        if key == "kind" and value not in {"vocal", "instrumental", "bgm", "unsure", "drama"}:
            raise ValueError("Unknown music type.")


def propose_fields(track, source, incoming, previous):
    """Only changed source fields propose edits; the reviewed draft never moves implicitly."""
    pending = track.setdefault("pending_suggestions", {}).setdefault(source, {})
    reviewed = track["suggestions"] | track["edits"]
    for field in previous.keys() - incoming.keys():
        pending.pop(field, None)  # Missing evidence is not an instruction to erase a reviewed value.
    for field, value in incoming.items():
        if previous.get(field) == value:
            continue
        proposal = {field:value}
        validate_fields(proposal, TRACK_FIELDS)
        current = credit_entries(field, reviewed[field]) if field in CREDIT_FIELDS else reviewed[field]
        if proposal[field] != current:
            pending[field] = proposal[field]
            track["publish_selected"] = False
        else:
            pending.pop(field, None)
    if not pending:
        track["pending_suggestions"].pop(source)


def now():
    return datetime.now(timezone.utc).isoformat()


def initial_review():
    tracks = []
    for track_id, position, title, kind in [
        (255, 1, "Get Over the World", "vocal"),
        (256, 2, "Get Over the World (Instrumental Ver.)", "instrumental"),
    ]:
        tracks.append({
            "id": str(track_id), "source_id": track_id, "included": True,
            "suggestions": {"title": title, "position": position, "disc": 1,
                            "kind": kind, "group": "", "performers": "",
                            "composer": "", "notes": ""},
            "edits": {}, "source": None, "source_status": "pending",
            "source_error": "", "source_fetched_at": None,
            "media": {"status": "pending"}, "tags": {},
        })
    tracks.append({
        "id": "drama", "source_id": None, "included": False,
        "suggestions": {"title": "Spoken drama", "position": 3, "disc": 1,
                        "kind": "drama", "group": "", "performers": "",
                        "composer": "", "notes": "Known from the release listing. Excluded from this music import."},
        "edits": {}, "source": None, "source_status": "reference",
        "source_error": "", "media": {"status": "excluded"}, "tags": {},
    })
    return {
        "album": {
            "id": "veritas-vol-2", "decision": "review",
            "suggestions": {"title": "青春あんさんぶる Vol.2 「ヴェリタス」",
                            "category": "青春あんさんぶる", "release_date": "2023-12-25",
                            "notes": ""},
            "edits": {}, "cover": {"status": "pending"},
        },
        "tracks": tracks,
        "gamekee": {"status": "pending", "url": "https://www.gamekee.com/ba/691994.html"},
        "release_reference": "https://ototoy.jp/_/default/p/1938374",
        "publication": {"status": "pending", "message": "Not published."},
        "job": {"running": False, "message": "Load source information to begin."},
        "saved_at": now(),
    }


class Store:
    def __init__(self, directory, initial=None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "reviews.sqlite3"
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS review (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO review VALUES (1, ?)",
                       (json.dumps(initial if initial is not None else initial_review(), ensure_ascii=False),))
        self.update(self._recover)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _recover(state):
        state.setdefault("publication", {"status": "pending", "message": "Not published."})
        state["album"]["suggestions"].setdefault("gamekee_url", state["gamekee"].get("url", ""))
        state["album"]["suggestions"].setdefault("gamekee_notes", "")
        publication = state["publication"]
        attempts = publication.get("attempt", {}).get("records", [])
        if (publication.get("status") == "running"
                or any(item["status"] == "sending" for item in attempts)
                or (state["job"].get("running") and state["job"].get("action") == "publish")):
            for item in attempts:
                if item["status"] == "sending":
                    item["status"] = "unconfirmed"
            publication.update(status="interrupted", message=(
                "Publication was interrupted. An unconfirmed request may already be saved. "
                "Check published state or retry with the same identities; earlier successes are retained."))
        if state["job"].get("running"):
            state["job"] = {"running": False, "message": "Local task was interrupted. Check the saved results before retrying."}
        for item in [state["album"]["cover"], *(t["media"] for t in state["tracks"])]:
            if item["status"] == "running":
                previous = item.pop("previous", {})
                item.clear()
                item.update(previous)
                item.update(status="ready" if previous.get("status") == "ready" else "failed",
                            error="Interrupted. Previous validated files are retained; retry to check for updates.")
        for order, track in enumerate(state["tracks"], 1):
            track.setdefault("publish_selected", track["included"] and track["source_id"] is not None)
            track["suggestions"].setdefault("display_order", order)

    def read(self):
        with self.lock, self.connect() as db:
            return json.loads(db.execute("SELECT payload FROM review WHERE id=1").fetchone()[0])

    def update(self, mutate):
        with self.lock, self.connect() as db:
            state = json.loads(db.execute("SELECT payload FROM review WHERE id=1").fetchone()[0])
            mutate(state)
            state["saved_at"] = now()
            db.execute("UPDATE review SET payload=? WHERE id=1", (json.dumps(state, ensure_ascii=False),))
            return state

    def view(self):
        state = deepcopy(self.read())
        state["album"]["fields"] = state["album"]["suggestions"] | state["album"]["edits"]
        cover = state["album"]["cover"]
        if cover.get("files"):
            cover["preview_url"] = "/media/cover/400"
        for track in state["tracks"]:
            track["fields"] = track["suggestions"] | track["edits"]
            for field in CREDIT_FIELDS:
                track["fields"][field] = credit_entries(field, track["fields"][field])
            if track["media"].get("path"):
                track["media"]["preview_url"] = f"/media/audio/{track['id']}"
        return state

    def save_edits(self, payload):
        album_fields = {"title", "category", "release_date", "notes", "gamekee_url", "gamekee_notes"}

        def mutate(state):
            album = payload.get("album", {})
            validate_fields(album, album_fields)
            state["album"]["edits"].update(album)
            tracks = payload.get("tracks", {})
            if not isinstance(tracks, dict):
                raise ValueError("Invalid track edits.")
            by_id = {t["id"]: t for t in state["tracks"]}
            for track_id, values in tracks.items():
                if track_id not in by_id or track_id == "drama":
                    raise ValueError("Unknown or excluded reference track.")
                validate_fields(values, TRACK_FIELDS)
                by_id[track_id]["edits"].update(values)
                if values.get("kind") == "drama":
                    by_id[track_id]["included"] = False
                    by_id[track_id]["publish_selected"] = False

        self.update(mutate)

    def review_suggestions(self, track_id, proposals, choice):
        if choice not in {"use", "keep"} or not isinstance(proposals, dict) or not proposals:
            raise ValueError("Choose incoming suggestions to use, or keep the reviewed values.")

        def mutate(state):
            track = find_track(state, track_id)
            pending = track.get("pending_suggestions", {})
            for source, fields in proposals.items():
                if not isinstance(fields, dict) or not fields:
                    raise ValueError("Choose the shown source fields.")
                for field, value in fields.items():
                    if field not in pending.get(source, {}) or pending[source][field] != value:
                        raise ValueError("The incoming suggestion changed. Compare the latest shown value first.")
                    reviewed = track["suggestions"] | track["edits"]
                    selected = {field:value if choice == "use" else reviewed[field]}
                    validate_fields(selected, TRACK_FIELDS)
                    track["edits"].update(selected)
                    track.setdefault("suggestion_reviews", []).append({"source":source, "field":field, "proposed":value,
                        "choice":choice, "reviewed_at":now()})
                    pending[source].pop(field)
                if not pending[source]:
                    pending.pop(source)
            track["publish_selected"] = False
            if (track["suggestions"] | track["edits"])["kind"] == "drama":
                track["included"] = False
        self.update(mutate)


def find_track(state, track_id):
    return next(t for t in state["tracks"] if t["id"] == str(track_id))
