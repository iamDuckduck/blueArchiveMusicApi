"""Kivo index discovery and remembered choices, separate from reviewed release fields."""

import json
import re
import sqlite3
import threading
import uuid
from collections import defaultdict
from contextlib import closing, contextmanager
from pathlib import Path
from urllib.parse import urlparse

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
            by_label = {c["source_album"]: c for c in candidates.values() if not c.get("manual")}
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
                                    change_count=len(c["changes"]), seen_in_latest_scan=c["seen_in_latest_scan"],
                                    redirect_to=c.get("redirect_to"), manual=c.get("manual", False),
                                    mapped_track_count=len(c.get("mapped_records", {})))
                               for c in state["candidates"].values()]}

    def saved_reviews(self):
        """List existing drafts without opening/recovering or creating a Store."""
        locations = [(self.directory / "reviews.sqlite3", "/")]
        for identity, candidate in self.read()["candidates"].items():
            if (identity == "veritas-vol-2" or candidate.get("redirect_to")
                    or candidate["kind"] != "release_candidate" or candidate["decision"] == "grouping"):
                continue
            database = (self.directory / "releases" / identity / "reviews.sqlite3").resolve()
            if database.is_relative_to(self.directory / "releases"):
                locations.append((database, f"/albums/{identity}/"))
        result = []
        for database, url in locations:
            if not database.is_file():
                continue
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
                row = connection.execute("SELECT payload FROM review WHERE id=1").fetchone()
            saved = json.loads(row[0])
            fields = saved["album"]["suggestions"] | saved["album"]["edits"]
            result.append({"title": fields["title"], "category": fields["category"],
                           "track_count": len(saved["tracks"]), "url": url})
        return sorted(result, key=lambda review: review["title"].casefold())

    def decide(self, identity, decision):
        if decision not in {"review", "included", "skipped", "grouping"}:
            raise ValueError("Choose review, included, skipped or grouping.")
        if self.job_lock.locked():
            raise ValueError("Wait for the current local job to finish.")

        def mutate(state):
            candidate = state["candidates"].get(identity)
            if candidate is None:
                raise ValueError("Unknown candidate.")
            if candidate.get("redirect_to"):
                raise ValueError("This source label is linked to an existing release. Review that release instead.")
            if decision == "included" and candidate["kind"] in {"source_grouping", "unresolved"}:
                raise ValueError("Identify the official music and create a named collection first; a broad source grouping is not automatically an album.")
            candidate.update(decision=decision, reviewed_at=now())
        return self.update(mutate)

    def create_release(self, payload):
        if self.job_lock.locked():
            raise ValueError("Wait for the local job to finish.")
        identity = payload.get("id")
        try:
            if str(uuid.UUID(identity)) != identity:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ValueError("A stable UUID is required for this release.")
        title, category = payload.get("title"), payload.get("category")
        reference = payload.get("reference", "")
        if not all(isinstance(v, str) and v.strip() and len(v) <= 255 for v in [title, category]):
            raise ValueError("Enter an album, single, or collection title and category (up to 255 characters).")
        if payload.get("official") is not True:
            raise ValueError("Confirm this collection contains identified official music, not just a broad source label.")
        if not isinstance(reference, str) or len(reference) > 2000:
            raise ValueError("Invalid release reference.")
        if reference and (urlparse(reference).scheme != "https" or not urlparse(reference).hostname or urlparse(reference).username):
            raise ValueError("Release references must be public HTTPS URLs.")

        def mutate(state):
            existing = state["candidates"].get(identity)
            if existing:
                if not existing.get("manual") or existing["source_album"] != title.strip():
                    raise ValueError("This release identity is already used. Open the saved release.")
                return
            timestamp = now()
            state["candidates"][identity] = {"id": identity, "source_album": title.strip(), "category": category.strip(),
                "reference": reference, "kind": "release_candidate", "manual": True, "decision": "review",
                "first_seen": timestamp, "records": [], "previous_records": [], "changes": [],
                "seen_in_latest_scan": False, "mapped_records": {}}
        return self.update(mutate)

    def map_tracks(self, source_id, target_id, track_ids):
        if self.job_lock.locked():
            raise ValueError("Wait for the local job to finish.")
        if not isinstance(source_id, str) or not isinstance(target_id, str):
            raise ValueError("Choose a source and target release.")
        if not isinstance(track_ids, list) or not track_ids or any(type(i) is not int for i in track_ids):
            raise ValueError("Select source track IDs to map.")

        def mutate(state):
            source = state["candidates"].get(source_id)
            target = state["candidates"].get(target_id)
            if not source or not target or target["kind"] != "release_candidate" or target.get("redirect_to") or target["decision"] == "grouping":
                raise ValueError("Choose a source and an identified target release, not another grouping.")
            available = {row["id"]: row for row in self.release_records(state, source)}
            if any(i not in available for i in track_ids):
                raise ValueError("One selected track is not present in this saved source. Reload the candidate.")
            mapped = target.setdefault("mapped_records", {})
            for identity in track_ids:
                mapped.setdefault(str(identity), {"source_candidate": source_id, "record": available[identity], "mapped_at": now()})
        return self.update(mutate)

    def link_release(self, source_id, target_id):
        """Resolve a duplicate/renamed source label without inventing another public release."""
        if self.job_lock.locked():
            raise ValueError("Wait for the local job to finish.")
        if not isinstance(source_id, str) or not isinstance(target_id, str):
            raise ValueError("Choose a source and target release.")

        def mutate(state):
            source, target = (state["candidates"].get(i) for i in [source_id, target_id])
            if (not source or not target or source_id == target_id or source.get("manual")
                    or source["kind"] != "release_candidate" or target["kind"] != "release_candidate"
                    or target.get("redirect_to") or target["decision"] == "grouping"):
                raise ValueError("Choose two release candidates, with an existing release as the target.")
            source_path = self.directory if source_id == "veritas-vol-2" else self.directory / "releases" / source_id
            if (source_path / "reviews.sqlite3").exists():
                raise ValueError("This source already has a saved review. Keep it intact; map individual tracks instead of merging reviews.")
            if any(c.get("redirect_to") == source_id for c in state["candidates"].values()):
                raise ValueError("This release already owns linked source labels. Use it as the target.")
            if source.get("redirect_to") not in {None, target_id}:
                raise ValueError("This source is already linked to a different release.")
            source.update(redirect_to=target_id, decision="linked", reviewed_at=now())
        return self.update(mutate)

    @staticmethod
    def release_records(state, candidate):
        rows = {r["id"]: r for r in candidate["records"]}
        for linked in state["candidates"].values():
            if linked.get("redirect_to") == candidate["id"]:
                rows.update({r["id"]: r for r in linked["records"]})
        latest = {r["id"]: r for r in state["snapshots"][-1]["records"]} if state["snapshots"] else {}
        for key, mapped in candidate.get("mapped_records", {}).items():
            identity = int(key)
            rows[identity] = latest.get(identity, mapped["record"])
        return list(rows.values())

    def open_review(self, identity):
        catalog = self.read()
        candidate = catalog["candidates"].get(identity)
        if candidate is None:
            raise ValueError("Unknown candidate.")
        if candidate.get("redirect_to"):
            raise ValueError("This source label is linked to another release. Open the target release.")
        if candidate["kind"] != "release_candidate" or candidate["decision"] == "grouping":
            raise ValueError("This is a broad or unidentified source group. Create a named collection for identified official music, then map its tracks.")
        label = candidate["source_album"]
        category = candidate.get("category") or next((name for name in ["青春あんさんぶる", "絆ダイアローグ", "OST"] if name in label), "")
        initial = {"album": {"id": identity, "decision": candidate["decision"],
                              "suggestions": {"title": label, "category": category, "release_date": "", "notes": ""},
                              "edits": {}, "cover": {"status": "pending"}},
                   "tracks": [draft_track(record) for record in self.release_records(catalog, candidate)],
                   "gamekee": {"status": "pending", "url": ""}, "release_reference": candidate.get("reference", ""),
                   "publication": {"status": "pending", "message": "Not published."},
                   "job": {"running": False, "message": "Select music tracks, then load source details."}, "saved_at": now()}
        directory = self.directory if identity == "veritas-vol-2" else self.directory / "releases" / identity
        store = Store(directory, initial=initial)
        store.update(lambda s: s["album"].update(decision=candidate["decision"]))
        self.sync_review(store, candidate)
        return store

    def sync_review(self, store, candidate=None):
        saved = store.read()
        catalog = self.read()
        candidate = candidate or catalog["candidates"].get(saved["album"]["id"])
        if candidate is None or saved["job"].get("running"):
            return
        records = self.release_records(catalog, candidate)
        latest_ids = {r["id"] for r in catalog["snapshots"][-1]["records"]} if catalog["snapshots"] else set()
        known_ids = {t["source_id"] for t in saved["tracks"] if t["source_id"] is not None} | {r["id"] for r in records}
        missing_ids = sorted(known_ids - latest_ids)
        if saved.get("last_index") == records and saved.get("missing_index_ids") == missing_ids:
            return

        def mutate(state):
            tracks = {t["source_id"]: t for t in state["tracks"] if t["source_id"] is not None}
            incoming = {r["id"]: r for r in records}
            next_order = max(((t["suggestions"] | t["edits"])["display_order"] for t in state["tracks"]), default=0) + 1
            for identity, record in incoming.items():
                if state["album"]["id"] == "veritas-vol-2" and identity == 257:
                    reference = next((t for t in state["tracks"] if t["id"] == "drama"), None)
                    if reference is not None:
                        reference["index"] = record
                        continue
                if identity not in tracks:
                    added = draft_track(record)
                    added["suggestions"]["display_order"] = next_order
                    next_order += 1
                    state["tracks"].append(added)
                elif "index" not in tracks[identity]:
                    tracks[identity]["index"] = record
                elif tracks[identity]["index"] != record:
                    track = tracks[identity]
                    track["pending_index"] = record
                    track["publish_selected"] = False
                    track["index_warning"] = "Source index changed. Compare the incoming record and explicitly reload details; saved corrections are retained."
                else:
                    tracks[identity].pop("pending_index", None)
                    tracks[identity].pop("index_warning", None)
            for identity, track in tracks.items():
                if identity not in incoming or identity in missing_ids:
                    track["missing_index"] = True
                else:
                    track.pop("missing_index", None)
            state["last_index"] = records
            state["missing_index_ids"] = missing_ids
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
