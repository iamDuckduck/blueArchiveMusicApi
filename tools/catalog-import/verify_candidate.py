"""Smoke-test a prepared candidate ONLY in the fixed local PostgreSQL/MinIO verifier.

--tracks selects files for a disposable test copy, not publication approval for
the saved review. No source fetching, development R2, or production writes occur.
"""

import argparse
import json
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import time
import uuid
from unittest.mock import patch

from media import digest
from publisher import Publisher
from store import Store
import verify_live as isolated


def validate_review(directory, track_ids):
    directory = Path(directory).resolve()
    database = directory / "reviews.sqlite3"
    if not database.is_file():
        raise ValueError("Choose an existing prepared review containing reviews.sqlite3.")
    if (not track_ids or any(type(identity) is not int or identity < 1 for identity in track_ids)
            or len(set(track_ids)) != len(track_ids)):
        raise ValueError("Select distinct positive source track IDs with --tracks.")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        row = connection.execute("SELECT payload FROM review WHERE id=1").fetchone()
    if row is None:
        raise ValueError("The saved review is empty.")
    state = json.loads(row[0])
    if state["album"].get("decision") != "included" or state.get("job", {}).get("running"):
        raise ValueError("Include the reviewed candidate and finish any running job before verification.")
    tracks = [track for track in state["tracks"] if track.get("source_id") in track_ids]
    if len(tracks) != len(track_ids) or {track["source_id"] for track in tracks} != set(track_ids):
        raise ValueError("Every selected source track must exist exactly once in this review.")
    for track in tracks:
        if not track["included"] or (track["suggestions"] | track["edits"])["kind"] == "drama":
            raise ValueError("Select included music tracks only; spoken drama is excluded.")
        if track.get("pending_suggestions") or track.get("pending_index"):
            raise ValueError("Resolve incoming source changes before verification.")
        if track["media"].get("status") != "ready":
            raise ValueError("Prepare every selected track before verification.")
    cover = state["album"]["cover"]
    if cover.get("status") != "ready" or not {"original", "400", "800"} <= cover.get("files", {}).keys():
        raise ValueError("Prepare the original cover and both display copies before verification.")
    files = set()
    for item in [cover["files"][key] for key in ["original", "400", "800"]] + [track["media"] for track in tracks]:
        relative = Path(item.get("path", ""))
        target = (directory / relative).resolve()
        if relative.is_absolute() or not target.is_relative_to(directory / "media") or not target.is_file():
            raise ValueError("Prepared media must exist inside this review's media directory.")
        if digest(target) != item.get("sha256"):
            raise ValueError("Prepared media changed or lacks a validation hash; prepare it again.")
        relative = target.relative_to(directory)
        item["path"] = relative.as_posix()
        files.add(relative)
    # These choices affect only the parsed snapshot and its isolated test copy.
    state["tracks"] = tracks
    for track in tracks:
        track["publish_selected"] = True
    state["publication"] = {"status": "pending", "message": "Isolated verification copy only."}
    return state, sorted(files)


def create_review_copy(directory, track_ids, run):
    state, files = validate_review(directory, track_ids)
    run.mkdir(parents=True, exist_ok=False)
    review = run / "review"
    for relative in files:
        destination = review / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(directory) / relative, destination)
    state["album"]["id"] = "verify-" + run.name
    store = Store(review, initial=state)
    validate_review(review, track_ids)  # Recheck copied bytes before starting the backend.
    Publisher(store, isolated.BASE, isolated.KEY)._validate(store.view())
    return review, files


def fingerprints(directory, files):
    return {relative.as_posix(): digest(Path(directory) / relative)
            for relative in [Path("reviews.sqlite3"), *files]}


def counts():
    return [int(value) for value in isolated.sql(
        "SELECT (SELECT count(*) FROM album), (SELECT count(*) FROM song)").split("|")]


def receipt_identities(store):
    receipts = store.read()["publication"]["destinations"][isolated.BASE]["receipts"]
    return {key: {field: value.get(field) for field in ["albumId", "songId", "revision"]}
            for key, value in receipts.items()}


def check_delivery(store, album_id):
    response = isolated.HTTP.get(isolated.BASE + f"/user/albums/{album_id}/songs", timeout=15, allow_redirects=False)
    response.raise_for_status()
    album = response.json()
    draft = store.view()
    assert album["title"] == draft["album"]["fields"]["title"].strip()
    assert album["category"] == draft["album"]["fields"]["category"]
    assert album["releaseDate"] == (draft["album"]["fields"]["release_date"] or None)
    receipts = receipt_identities(store)
    expected = {receipts[track["id"]]["songId"]: track for track in draft["tracks"]}
    songs = album["songList"]
    assert len(songs) == len(expected) and {song["id"] for song in songs} == set(expected)
    assert [song["displayOrder"] for song in songs] == sorted(track["fields"]["display_order"] for track in expected.values())
    for song in songs:
        track = expected[song["id"]]
        fields = track["fields"]
        assert (song["title"], song["discNumber"], song["trackNumber"], song["displayOrder"]) == (
            fields["title"].strip(), fields["disc"], fields["position"], fields["display_order"])
        with (store.directory / track["media"]["path"]).open("rb") as audio:
            prefix = audio.read(1024)
        response = isolated.HTTP.get(isolated.MEDIA + song["audioPath"], headers={"Range": f"bytes=0-{len(prefix) - 1}"},
                                     timeout=15, allow_redirects=False)
        assert response.status_code == 206 and response.headers.get("Content-Type", "").startswith("audio/")
        assert response.content == prefix
        response = isolated.HTTP.get(isolated.MEDIA + song["imagePath"], timeout=15, allow_redirects=False)
        assert response.status_code == 200 and response.headers.get("Content-Type") == "image/jpeg"
    response = isolated.HTTP.get(isolated.MEDIA + album["coverImagePath"], timeout=15, allow_redirects=False)
    assert response.status_code == 200 and response.headers.get("Content-Type") == "image/jpeg"
    return album


def verify(source_review, track_ids):
    if not isolated.JAR.is_file():
        raise RuntimeError("Build the backend jar before verification (do not clean target).")
    run = isolated.ROOT / "target" / ("catalog-candidate-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    _, source_files = validate_review(source_review, track_ids)
    before_source = fingerprints(source_review, source_files)
    review, _ = create_review_copy(source_review, track_ids, run)
    store = Store(review)
    report = {"status": "failed", "identity": store.read()["album"]["id"], "source_tracks": track_ids,
              "database": "catalog_import_verify", "storage": isolated.MEDIA, "source_hashes": before_source}
    process = None
    try:
        with (run / "backend.log").open("w", encoding="utf-8") as log, patch("publisher.requests", isolated.HTTP):
            process = isolated.start_server(log)
            before_counts, before_objects = counts(), isolated.objects()
            Publisher(store, isolated.BASE, isolated.KEY).publish()
            first = receipt_identities(store)
            after_counts, stable_objects = counts(), isolated.objects()
            assert after_counts == [before_counts[0] + 1, before_counts[1] + len(track_ids)]
            assert all(stable_objects.get(key) == value for key, value in before_objects.items())
            # Restart the review reader: retry must use persisted identities and baselines.
            store = Store(review)
            Publisher(store, isolated.BASE, isolated.KEY).publish()
            assert receipt_identities(store) == first, "Retry changed IDs or metadata revisions"
            assert counts() == after_counts, "Retry created duplicate catalog records"
            assert isolated.objects() == stable_objects, "Retry changed media keys or timestamps"
            assert all(item["status"] == "unchanged" for item in store.read()["publication"]["attempt"]["records"])
            album = check_delivery(store, first["album"]["albumId"])
            assert fingerprints(source_review, source_files) == before_source, "The source review or prepared files changed"
            report.update(status="passed", source_unchanged=True, records=first, album=album,
                          counts_before=before_counts, counts_after=after_counts,
                          new_object_count=len(stable_objects) - len(before_objects),
                          checks=["isolated test copy; owner publication selections untouched", "persisted review retry",
                                  "stable IDs, revisions, counts and media timestamps", "category and nullable official numbering",
                                  "public audio byte ranges and JPEG covers", "source SQLite/media SHA-256 unchanged"])
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        try:
            if process is not None:
                isolated.stop_server(process)
        finally:
            (run / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print("Evidence:", run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--tracks", type=int, nargs="+", required=True, help="Source IDs for the isolated test copy only")
    args = parser.parse_args()
    verify(args.review, args.tracks)


if __name__ == "__main__":
    main()
