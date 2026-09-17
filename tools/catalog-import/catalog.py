"""Kivo index discovery and remembered choices, separate from reviewed release fields."""

import json
import re
import sqlite3
import threading
import uuid
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

import requests

from sources import HEADERS
from store import Store, initial_review, now

KIVO_INDEX = "https://api.kivo.wiki/api/v1/musics/"


def draft_track(record):
    title = record["title"]
    kind = "drama" if re.search(r"ボイスドラマ|广播剧|廣播劇|voice drama|spoken drama", title, re.I) else "instrumental" if re.search(r"instrumental|off vocal", title, re.I) else "unsure"
    return {"id": str(record["id"]), "source_id": record["id"], "included": False, "publish_selected": False,
            "suggestions": {"title": record["title"], "position": None, "disc": None,
                            "kind": kind, "group": [], "performers": [], "composer": [], "notes": ""},
            "edits": {}, "source": None, "source_status": "pending", "source_error": "",
            "source_fetched_at": None, "media": {"status": "pending"}, "tags": {}, "index": record}


def fetch_index(progress=lambda message: None):
    """Accept a complete, consistent pagination run or leave the prior catalog alone."""
    records, seen, pages = [], set(), None
    page = 1
    while pages is None or page <= pages:
        progress(f"Reading Kivo index page {page}" + (f" of {pages}" if pages else ""))
        response = requests.get(KIVO_INDEX, params={"page": page, "page_size": 100},
                                headers=HEADERS, timeout=(10, 30), allow_redirects=False)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if payload.get("success") is not True or not isinstance(data, dict):
            raise ValueError("Kivo did not return a successful index. Saved candidates were not changed.")
        count, rows = data.get("max_page"), data.get("music")
        if type(count) is not int or not 1 <= count <= 500 or not isinstance(rows, list) or not rows:
            raise ValueError("Kivo returned an empty or invalid page. Saved candidates were not changed.")
        if pages is not None and pages != count:
            raise ValueError("Kivo pagination changed during this scan. Retry; saved candidates were not changed.")
        pages = count
        for row in rows:
            if (not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] < 1
                    or not isinstance(row.get("title"), str) or not row["title"].strip()
                    or not isinstance(row.get("album", ""), str)):
                raise ValueError("Kivo returned an invalid basic record. Saved candidates were not changed.")
            if row["id"] in seen:
                raise ValueError("Kivo repeated an ID across index pages. Retry the scan.")
            seen.add(row["id"])
            records.append(row)
        page += 1
    return records


class Catalog:
    def __init__(self, directory, job_lock=None):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "catalog.sqlite3"
        self.lock = threading.RLock()
        self.job_lock = job_lock or threading.Lock()
        self.thread = None
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS catalog (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO catalog VALUES (1, ?)", (json.dumps({
                "candidates": {}, "scan": {"running": False, "status": "pending", "message": "Scan Kivo to discover candidate releases."},
                "snapshots": [],
            }),))
        self.update(lambda state: state["scan"].update(running=False))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def read(self):
        with self.lock, self.connect() as db:
            return json.loads(db.execute("SELECT payload FROM catalog WHERE id=1").fetchone()[0])

    def update(self, mutate):
        with self.lock, self.connect() as db:
            state = json.loads(db.execute("SELECT payload FROM catalog WHERE id=1").fetchone()[0])
            mutate(state)
            db.execute("UPDATE catalog SET payload=? WHERE id=1", (json.dumps(state, ensure_ascii=False),))
            return state

    def merge(self, records):
        if not records:
            raise ValueError("An empty scan cannot replace the saved index.")
        groups = defaultdict(list)
        for row in records:
            groups[row.get("album", "").strip()].append(row)
        timestamp = now()
        sample = initial_review()
        review_db = self.directory / "reviews.sqlite3"
        if review_db.is_file():
            db = sqlite3.connect(f"file:{review_db.as_posix()}?mode=ro", uri=True)
            try:
                sample = json.loads(db.execute("SELECT payload FROM review WHERE id=1").fetchone()[0])
            finally:
                db.close()
        sample_label = next((t["source"]["album"] for t in sample["tracks"]
                             if (t.get("source") or {}).get("album")),
                            sample["album"]["suggestions"]["title"])

        def mutate(state):
            candidates = state["candidates"]
            by_label = {c["source_album"]: c for c in candidates.values()}
            changed = not state["snapshots"] or state["snapshots"][-1]["records"] != records
            if changed:
                state["snapshots"].append({"fetched_at": timestamp, "records": records})
            for candidate in candidates.values():
                candidate["seen_in_latest_scan"] = False
            for label, rows in groups.items():
                candidate = by_label.get(label)
                if candidate is None:
                    identity = "veritas-vol-2" if label == sample_label else str(uuid.uuid4())
                    kind = "unresolved" if not label else "source_grouping" if label == "游戏内曲目" else "release_candidate"
                    candidate = {"id": identity, "source_album": label, "kind": kind,
                                 "decision": sample["album"]["decision"] if identity == "veritas-vol-2" else "review",
                                 "first_seen": timestamp, "records": [], "previous_records": [], "changes": []}
                    candidates[identity] = candidate
                old = {r["id"]: r for r in candidate["records"]}
                incoming = {r["id"]: r for r in rows}
                changes = [{"id": key, "change": "new" if key not in old else "changed"}
                           for key, row in incoming.items() if old.get(key) != row]
                changes += [{"id": key, "change": "not_in_latest_index"} for key in old.keys() - incoming.keys()]
                if changes:
                    candidate["previous_records"] = candidate["records"]
                    candidate["records"] = rows
                    candidate["changes"] = changes
                    candidate["changed_at"] = timestamp
                candidate.update(last_seen=timestamp, seen_in_latest_scan=True)
            state["scan"].update(status="ready", running=False, checked_at=timestamp,
                                 message=f"Read {len(records)} source records in {len(groups)} candidate groups. No media prepared or published.")
        return self.update(mutate)

    def view(self):
        state = self.read()
        return {"scan": state["scan"], "snapshot_count": len(state["snapshots"]),
                "candidates": [dict(id=c["id"], source_album=c["source_album"], kind=c["kind"],
                                    decision=c["decision"], track_count=len(c["records"]),
                                    change_count=len(c["changes"]), seen_in_latest_scan=c["seen_in_latest_scan"])
                               for c in state["candidates"].values()]}

    def decide(self, identity, decision):
        if decision not in {"review", "included", "skipped", "grouping"}:
            raise ValueError("Choose review, included, skipped or grouping.")
        if self.job_lock.locked():
            raise ValueError("Wait for the current local job to finish.")

        def mutate(state):
            candidate = state["candidates"].get(identity)
            if candidate is None:
                raise ValueError("Unknown candidate.")
            if decision == "included" and candidate["kind"] in {"source_grouping", "unresolved"}:
                raise ValueError("Identify an official release for these tracks first; a source grouping is not an album.")
            candidate.update(decision=decision, reviewed_at=now())
        return self.update(mutate)

    def open_review(self, identity):
        candidate = self.read()["candidates"].get(identity)
        if candidate is None:
            raise ValueError("Unknown candidate.")
        if candidate["kind"] != "release_candidate" or candidate["decision"] == "grouping":
            raise ValueError("This is a source grouping or unidentified release, not an approved album candidate.")
        label = candidate["source_album"]
        category = next((name for name in ["青春あんさんぶる", "絆ダイアローグ", "OST"] if name in label), "")
        initial = {"album": {"id": identity, "decision": candidate["decision"],
                              "suggestions": {"title": label, "category": category, "release_date": "", "notes": ""},
                              "edits": {}, "cover": {"status": "pending"}},
                   "tracks": [draft_track(record) for record in candidate["records"]],
                   "gamekee": {"status": "pending", "url": ""}, "release_reference": "",
                   "publication": {"status": "pending", "message": "Not published."},
                   "job": {"running": False, "message": "Select music tracks, then load source details."}, "saved_at": now()}
        directory = self.directory if identity == "veritas-vol-2" else self.directory / "releases" / identity
        store = Store(directory, initial=initial)
        store.update(lambda s: s["album"].update(decision=candidate["decision"]))
        self.sync_review(store, candidate)
        return store

    def sync_review(self, store, candidate=None):
        saved = store.read()
        candidate = candidate or self.read()["candidates"].get(saved["album"]["id"])
        if candidate is None or saved["job"].get("running"):
            return
        if saved.get("last_index") == candidate["records"]:
            return

        def mutate(state):
            tracks = {t["source_id"]: t for t in state["tracks"] if t["source_id"] is not None}
            incoming = {r["id"]: r for r in candidate["records"]}
            for identity, record in incoming.items():
                if state["album"]["id"] == "veritas-vol-2" and identity == 257:
                    reference = next((t for t in state["tracks"] if t["id"] == "drama"), None)
                    if reference is not None:
                        reference["index"] = record
                        continue
                if identity not in tracks:
                    state["tracks"].append(draft_track(record))
                elif "index" not in tracks[identity]:
                    tracks[identity]["index"] = record
                elif tracks[identity]["index"] != record:
                    track = tracks[identity]
                    track["pending_index"] = record
                    track["index_warning"] = "Source index changed. Compare the incoming record and explicitly reload details; saved corrections are retained."
            for identity, track in tracks.items():
                if identity not in incoming:
                    track["index_warning"] = "Not in the latest source index. Saved track, files and publication are retained."
            state["last_index"] = candidate["records"]
        store.update(mutate)

    def start_scan(self):
        if not self.job_lock.acquire(blocking=False):
            raise ValueError("A local job is already running.")
        self.update(lambda s: s["scan"].update(running=True, status="running", message="Starting Kivo scan…"))

        def run():
            try:
                self.merge(fetch_index(lambda message: self.update(lambda s: s["scan"].update(message=message))))
            except Exception as error:
                self.update(lambda s: s["scan"].update(running=False, status="failed", message=str(error), checked_at=now()))
            finally:
                self.job_lock.release()
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
