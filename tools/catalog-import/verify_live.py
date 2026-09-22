"""Bounded, repeatable Veritas check. Writes ONLY the fixed catalog-verify environment.

Run compose.verify.yaml first, initialize its test bucket (README), then build the jar.
Uses a copied review and validated media; never mutates the owner's saved review.
"""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import sqlite3
import socket
import subprocess
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch

import requests

from publisher import Publisher, PublicationConflict
from store import Store

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:18082"
MEDIA = "http://127.0.0.1:19000/catalog-import-verify/"
KEY = "catalog-import-local-only"
JAR = ROOT / "target/blue_archive_music_api-0.0.1-SNAPSHOT.jar"
DOCKER = ["docker", "--host", "npipe:////./pipe/docker_engine" if os.name == "nt" else "unix:///var/run/docker.sock"]
HTTP = requests.Session()
HTTP.trust_env = False  # Local verification must not inherit HTTP proxies or .netrc credentials.


def local_environment():
    """Keep only OS necessities, never application, Java-option, or cloud settings."""
    allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR",
               "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "LANG", "LC_ALL"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


def server_arguments(java):
    return [str(java), "-jar", str(JAR),
        "--spring.config.location=classpath:/application.yaml,classpath:/application-catalog-verify.yaml",
        "--spring.profiles.active=catalog-verify", "--spring.profiles.include=",
        "--server.address=127.0.0.1", "--server.port=18082",
        "--spring.datasource.url=jdbc:postgresql://127.0.0.1:15433/catalog_import_verify",
        "--spring.datasource.username=catalog_verify", "--spring.datasource.password=catalog-verify-local-only",
        "--spring.flyway.url=jdbc:postgresql://127.0.0.1:15433/catalog_import_verify",
        "--spring.flyway.user=catalog_verify", "--spring.flyway.password=catalog-verify-local-only",
        "--spring.flyway.enabled=true", "--spring.flyway.baseline-on-migrate=false", "--spring.flyway.validate-on-migrate=true",
        "--spring.jpa.hibernate.ddl-auto=none", "--spring.jpa.show-sql=false",
        "--spring.docker.compose.enabled=false", "--app.catalog-media.mode=r2",
        "--cloudflare.r2.endpoint=http://127.0.0.1:19000", "--cloudflare.r2.bucket=catalog-import-verify",
        "--cloudflare.r2.access-key=catalog_verify", "--cloudflare.r2.secret-key=catalog-verify-local-only",
        "--app.admin.api-key=" + KEY]


def validate_review(directory):
    """Read without Store initialization/recovery, which would change the owner's SQLite file."""
    directory = Path(directory).resolve()
    database = directory / "reviews.sqlite3"
    if not database.is_file():
        raise ValueError("Choose the prepared Veritas review directory containing reviews.sqlite3.")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source:
        row = source.execute("SELECT payload FROM review WHERE id=1").fetchone()
    if row is None:
        raise ValueError("The source review is empty.")
    state = json.loads(row[0])
    if state["album"]["id"] != "veritas-vol-2" or state["album"].get("decision") != "included":
        raise ValueError("This verification requires the included, reviewed Veritas sample, not demo data.")
    if state.get("job", {}).get("running"):
        raise ValueError("Wait for review preparation to finish before verification.")
    tracks = [track for track in state["tracks"] if track["included"]]
    if (len(tracks) != 2 or {(track["id"], track["source_id"]) for track in tracks} != {("255", 255), ("256", 256)}
            or not all(track.get("publish_selected") for track in tracks)):
        raise ValueError("Include and select exactly the reviewed Veritas music tracks 255 and 256.")
    if any(track.get("pending_suggestions") for track in tracks):
        raise ValueError("Review incoming source suggestions before verification.")
    cover = state["album"]["cover"]
    if cover.get("status") != "ready" or not {"original", "400", "800"} <= cover.get("files", {}).keys():
        raise ValueError("Prepare the Veritas cover before verification.")
    if any(track["media"].get("status") != "ready" for track in tracks):
        raise ValueError("Prepare both Veritas music tracks before verification.")
    items = [cover["files"][key] for key in ["original", "400", "800"]] + [track["media"] for track in tracks]
    files = []
    for item in items:
        relative = Path(item.get("path", ""))
        target = (directory / relative).resolve()
        if (relative.is_absolute() or not target.is_relative_to(directory / "media") or not target.is_file()):
            raise ValueError("A prepared media path is missing or outside this review's media directory.")
        with target.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != item.get("sha256"):
                raise ValueError("Prepared media changed or lacks a validation hash; prepare it again.")
        relative = target.relative_to(directory)
        item["path"] = relative.as_posix()  # Normalize the copied snapshot, never the owner's SQLite row.
        files.append(relative)
    return state, files


def create_review_copy(directory, run):
    # Fail before creating a run or copying any unreviewed files.
    state, files = validate_review(directory)
    run.mkdir(parents=True, exist_ok=False)
    review = run / "review"
    for relative in set(files):
        destination = review / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(directory) / relative, destination)
    Store(review, initial=state)
    validate_review(review)  # Recheck copied bytes before any backend can start.
    return review


def sql(query):
    result = subprocess.run([
        *DOCKER, "exec", "catalog-import-verify-postgres-1", "psql", "-U", "catalog_verify",
        "-d", "catalog_import_verify", "-At", "-v", "ON_ERROR_STOP=1", "-c", query,
    ], capture_output=True, text=True, check=True, encoding="utf-8", env=local_environment())
    return result.stdout.strip()


def objects():
    result = subprocess.run([
        *DOCKER, "exec", "-e", "MC_HOST_verify=http://catalog_verify:catalog-verify-local-only@127.0.0.1:9000",
        "catalog-import-verify-storage-1", "mc", "ls", "--recursive", "--json", "verify/catalog-import-verify",
    ], capture_output=True, text=True, check=True, encoding="utf-8", env=local_environment())
    return {row["key"]: (row["lastModified"], row["size"], row.get("etag"))
            for line in result.stdout.splitlines() if (row := json.loads(line)).get("type") == "file"}


def catalog():
    return json.loads(sql("SELECT coalesce(json_agg(row_to_json(s) ORDER BY id), '[]') FROM "
                          "(SELECT id, album_id, source_track_id, audio_path, image_path, play_count FROM song) s"))


def start_server(log):
    if not JAR.is_file():
        raise RuntimeError("Build the backend jar with ./mvnw package -DskipTests before verification (do not clean target).")
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", 18082)) == 0:
            raise RuntimeError("Port 18082 is already in use; refusing to use an unverified server")
    environment = local_environment()
    settings = subprocess.run(["java", "-XshowSettings:properties", "-version"],
                              capture_output=True, text=True, check=True, env=environment)
    match = re.search(r"^\s*java.home = (.+)$", settings.stderr, re.MULTILINE)
    if not match:
        raise RuntimeError("Cannot locate the real Java runtime from java.home.")
    java_home = match.group(1).strip()
    # Launch the real binary, not Oracle's Windows shim (which spawns a detached child).
    java = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
    process = subprocess.Popen(server_arguments(java), cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=environment,
       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError("Verification server exited; inspect backend.log")
            try:
                if HTTP.get(BASE + "/user/categories/details", timeout=1, allow_redirects=False).status_code == 200:
                    return process
            except requests.RequestException:
                pass
            time.sleep(0.5)
        raise RuntimeError("Verification server did not become ready; inspect backend.log")
    except BaseException:
        stop_server(process)
        raise


def stop_server(process):
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=Path(__file__).parent / "data")
    args = parser.parse_args()
    with patch("publisher.requests", HTTP):
        verify(args.review)


def verify(source_review):
    if not JAR.is_file():
        raise RuntimeError("Build the backend jar before verification (do not clean target).")
    run = ROOT / "target" / ("catalog-live-" + time.strftime("%Y%m%d-%H%M%S"))
    review = create_review_copy(source_review, run)
    store = Store(review)
    # A fresh appearance identity makes partial-publication assertions repeatable without deleting data.
    identity = "verify-" + run.name
    store.update(lambda s: s["album"].update(id=identity))
    store.update(lambda s: s.update(publication={"status": "pending", "tracks": {}}))
    publisher = Publisher(store, BASE, KEY)
    real_put = HTTP.put
    report = {"identity": identity, "database": "catalog_import_verify", "storage": MEDIA}
    with (run / "backend.log").open("w", encoding="utf-8") as log:
        process = start_server(log)
        try:
            report["migrations"] = sql("SELECT string_agg(version, ',' ORDER BY installed_rank) "
                                       "FROM flyway_schema_history WHERE success")
            assert report["migrations"].split(",") == [f"1.{number}" for number in range(1, 11)]

            def lose_response(*a, **kw):
                response = real_put(*a, **kw)
                response.raise_for_status()
                raise requests.Timeout("Injected lost successful album response")

            with patch("publisher.requests.put", side_effect=lose_response):
                try:
                    publisher.publish()
                except requests.Timeout:
                    pass
                else:
                    raise AssertionError("Lost response injection was not reached")
            album_id = int(sql(f"SELECT id FROM album WHERE source_album_id='{identity}'"))
            first_objects = objects()

            def fail_second_track(url, **kw):
                if url.endswith("/tracks/256"):
                    metadata = json.loads(kw["files"]["metadata"][1])
                    metadata["kind"] = "drama"
                    kw["files"]["metadata"] = (None, json.dumps(metadata), "application/json")
                return real_put(url, **kw)

            with patch("publisher.requests.put", side_effect=fail_second_track):
                try:
                    publisher.publish()
                except ValueError as error:
                    assert "400" in str(error), str(error)
                else:
                    raise AssertionError("Expected real backend rejection for track 256")
            partial = [s for s in catalog() if s["album_id"] == album_id]
            assert len(partial) == 1 and partial[0]["source_track_id"] == "255", partial
            assert str(store.read()["publication"]["tracks"]["255"]["songId"]) == str(partial[0]["id"])
            assert all(objects()[key] == value for key, value in first_objects.items())
            report["partial_track_id"] = partial[0]["id"]
            response = HTTP.post(BASE + f"/user/song/{partial[0]['id']}/play", timeout=10, allow_redirects=False)
            response.raise_for_status()
            before_restart = objects()
            stop_server(process)
            process = start_server(log)
            publisher = Publisher(Store(review), BASE, KEY)
            publisher.publish()
            complete = [s for s in catalog() if s["album_id"] == album_id]
            assert len(complete) == 2
            assert next(s for s in complete if s["source_track_id"] == "255")["play_count"] == 1
            assert all(objects()[key] == value for key, value in before_restart.items())
            stable_objects = objects()
            publisher.publish()
            assert [s for s in catalog() if s["album_id"] == album_id] == complete
            assert objects() == stable_objects, "Unchanged publication replaced or added media"
            album = HTTP.get(BASE + f"/user/albums/{album_id}/songs", timeout=10, allow_redirects=False).json()
            assert [s["trackNumber"] for s in album["songList"]] == [1, 2]
            assert [s["displayOrder"] for s in album["songList"]] == [1, 2]
            expected = store.view()["tracks"]
            for song, draft in zip(album["songList"], [t for t in expected if t["included"]]):
                assert song["title"] == draft["fields"]["title"]
                assert set(song["composers"]) == set(draft["fields"]["composer"])
                assert set(draft["fields"]["group"]) <= set(song["artists"])
                response = HTTP.get(MEDIA + song["audioPath"], headers={"Range": "bytes=0-1023"}, timeout=15, allow_redirects=False)
                assert response.status_code == 206 and response.headers["Content-Type"] == "audio/mpeg"
                assert len(response.content) == 1024
                assert HTTP.get(MEDIA + song["imagePath"], timeout=10, allow_redirects=False).headers["Content-Type"] == "image/jpeg"
            assert HTTP.get(MEDIA + album["coverImagePath"], timeout=10, allow_redirects=False).headers["Content-Type"] == "image/jpeg"
            # Exercise the new ordering contract on this isolated appearance, then restore the sample.
            # Display sequence is independent of nullable official numbering and known disc/track gaps.
            order_fields = {t["id"]:{key:t["fields"][key] for key in ["disc", "position", "display_order"]}
                            for t in store.view()["tracks"] if t["source_id"] in [255, 256]}
            store.save_edits({"tracks":{"255":{"disc":None, "position":None, "display_order":20},
                                        "256":{"disc":2, "position":4, "display_order":10}}})
            publisher.publish()
            reordered = HTTP.get(BASE + f"/user/albums/{album_id}/songs", timeout=10, allow_redirects=False).json()["songList"]
            assert [s["displayOrder"] for s in reordered] == [10, 20]
            assert [s["trackNumber"] for s in reordered] == [4, None]
            assert [s["discNumber"] for s in reordered] == [2, None]
            assert {s["id"] for s in reordered} == {s["id"] for s in complete}
            assert objects() == stable_objects
            report["ordering_case"] = [{key:s[key] for key in ["id", "displayOrder", "discNumber", "trackNumber"]}
                                       for s in reordered]
            store.save_edits({"tracks":order_fields})
            publisher.publish()
            assert [s for s in catalog() if s["album_id"] == album_id] == complete
            assert objects() == stable_objects
            # Simulate another review copy publishing a correction from the same earlier baseline.
            earlier_receipt = store.read()["publication"]["destinations"][BASE]["receipts"]["255"]
            track_payload = {}
            def newer_copy(url, **kw):
                if url.endswith("/tracks/255"):
                    metadata = json.loads(kw["files"]["metadata"][1])
                    track_payload.update(metadata)
                    metadata["title"] = "Newer isolated correction"
                    kw["files"]["metadata"] = (None, json.dumps(metadata), "application/json")
                return real_put(url, **kw)
            with patch("publisher.requests.put", side_effect=newer_copy):
                publisher.publish()
            # Restore only the old local baseline, without falsifying this attempt's progress.
            store.update(lambda saved: saved["publication"]["destinations"][BASE]["receipts"].update({"255": earlier_receipt}))
            try:
                publisher.publish()
            except PublicationConflict:
                pass
            else:
                raise AssertionError("A stale draft overwrote the newer correction")
            publisher.observe_published()
            assert publisher._headers("255")["X-Catalog-Revision"] == earlier_receipt["revision"]
            current = store.read()["publication"]["destinations"][BASE]["observed"]["255"]
            assert current["metadata"]["title"] == "Newer isolated correction"
            assert objects() == stable_objects
            publisher.accept_baseline("255", current["revision"])
            store.update(lambda s: next(t for t in s["tracks"] if t["id"] == "255").update(publish_selected=True))
            publisher.publish()  # Explicit reconciliation restores the sample's reviewed fields.
            assert [s for s in catalog() if s["album_id"] == album_id] == complete
            assert objects() == stable_objects
            report["conflict_case"] = {"trackId":current["songId"], "stale_edit_rejected":True,
                                       "read_did_not_advance_baseline":True, "explicit_reconciliation":True}
            baseline = publisher._headers("255")
            start = threading.Barrier(2)
            audio_item = next(t for t in store.read()["tracks"] if t["id"] == "255")["media"]
            def concurrent_change(title):
                with publisher._open(audio_item) as audio:
                    start.wait(timeout=5)
                    response = real_put(f"{BASE}/admin/catalog-import/kivo/albums/{identity}/tracks/255",
                        headers=baseline, files={
                            "metadata":(None, json.dumps(track_payload | {"title":title}), "application/json"),
                            "audio":(Path(audio.name).name, audio, "audio/mpeg")}, timeout=30, allow_redirects=False)
                    return response.status_code
            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(concurrent_change, ["Concurrent draft A", "Concurrent draft B"]))
            assert sorted(outcomes) == [200, 409], outcomes
            assert objects() == stable_objects
            publisher.observe_published()
            latest = store.read()["publication"]["destinations"][BASE]["observed"]["255"]
            publisher.accept_baseline("255", latest["revision"])
            store.update(lambda s: next(t for t in s["tracks"] if t["id"] == "255").update(publish_selected=True))
            publisher.publish()
            restored = HTTP.get(BASE + f"/user/albums/{album_id}/songs", timeout=10, allow_redirects=False).json()["songList"]
            expected_titles = [t["fields"]["title"] for t in store.view()["tracks"] if t["included"]]
            assert [s["title"] for s in restored] == expected_titles
            assert [s for s in catalog() if s["album_id"] == album_id] == complete
            assert objects() == stable_objects
            report["conflict_case"]["concurrent_statuses"] = sorted(outcomes)
            report.update(albumId=album_id, songs=complete, checks=["Flyway migration chain validated; existing test data retained", "lost album response",
                          "partial release", "restart retry", "stable IDs and play count", "credits and order",
                          "unknown official numbers and explicit display order (sample restored)",
                          "stale edit rejected and explicit baseline reconciliation",
                          "concurrent PostgreSQL writes: one success, one conflict",
                          "unchanged object timestamps/keys", "HTTP audio range and cover MIME"])
            (run / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print("Evidence:", run)
        finally:
            if process.poll() is None:
                stop_server(process)


if __name__ == "__main__":
    main()
