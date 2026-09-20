"""Verify structured credits/search in a separate local test database, never R2.

Requires the existing local catalog-import-verify PostgreSQL/MinIO services and
an included prepared Veritas review. Creates/retains catalog_credits_verify_<id>;
the original catalog_import_verify database and source review are not modified.
"""
import argparse
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
import uuid
from unittest.mock import patch

from media import digest
from publisher import Publisher
from store import Store
import verify_live as base

BASE = "http://127.0.0.1:18084"
DATABASE = "catalog_credits_verify"


def sql(query, database):
    if database != "postgres" and not re.fullmatch(r"catalog_credits_verify_[0-9a-f]{8}", database):
        raise ValueError("Use only a generated local credits-verification database.")
    result = subprocess.run([*base.DOCKER, "exec", "catalog-import-verify-postgres-1", "psql", "-U", "catalog_verify",
                             "-d", database, "-At", "-v", "ON_ERROR_STOP=1", "-c", query],
                            capture_output=True, text=True, encoding="utf-8", check=True, env=base.local_environment())
    return result.stdout.strip()


def server_arguments(java, database):
    if not re.fullmatch(r"catalog_credits_verify_[0-9a-f]{8}", database):
        raise ValueError("Use only a generated local credits-verification database.")
    # Reuse the verifier's complete isolation settings; change only this test's DB/port.
    arguments = [arg.replace("/catalog_import_verify", "/" + database).replace("--server.port=18082", "--server.port=18084")
                 for arg in base.server_arguments(java)]
    arguments.append("--app.cors.allowed-origins=http://127.0.0.1:15174")
    return arguments


def start_server(log, database):
    server_arguments("java", database)  # Reject a non-test database before any process starts.
    if not base.JAR.is_file():
        raise RuntimeError("Run mvn package on this credits branch first; do not clean target.")
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", 18084)) == 0:
            raise RuntimeError("Port 18084 is already in use; refusing to reuse another server.")
    environment = base.local_environment()
    settings = subprocess.run(["java", "-XshowSettings:properties", "-version"],
                              capture_output=True, text=True, check=True, env=environment)
    java_home = re.search(r"^\s*java.home = (.+)$", settings.stderr, re.M).group(1).strip()
    java = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
    process = subprocess.Popen(server_arguments(java, database), cwd=base.ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise RuntimeError("Credits backend stopped; inspect backend.log")
            try:
                if base.HTTP.get(BASE + "/user/categories/details", timeout=1, allow_redirects=False).status_code == 200:
                    return process
            except base.requests.RequestException:
                pass
            time.sleep(.5)
        raise RuntimeError("Credits backend did not become ready")
    except BaseException:
        base.stop_server(process)
        raise


def api(method, path, **kwargs):
    response = base.HTTP.request(method, BASE + path, headers={"X-Admin-Api-Key": base.KEY},
                                 timeout=30, allow_redirects=False, **kwargs)
    response.raise_for_status()
    return response.json()


def receipt_identities(store):
    receipts = store.read()["publication"]["destinations"][BASE]["receipts"]
    return {key: {field: value.get(field) for field in ["albumId", "songId", "revision"]}
            for key, value in receipts.items()}


def verify(source):
    if not base.JAR.is_file():
        raise RuntimeError("Build the credits branch first.")
    state, files = base.validate_review(source)
    source_hashes = {str(path): digest(source / path) for path in [Path("reviews.sqlite3"), *files]}
    run = base.ROOT / "target" / ("credits-live-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
    review = base.create_review_copy(source, run)
    store = Store(review)
    identity = "verify-" + run.name
    store.update(lambda saved: saved.update(publication={"status": "pending", "tracks": {}}))
    store.update(lambda saved: saved["album"].update(id=identity))
    database = DATABASE + "_" + uuid.uuid4().hex[:8]
    sql(f"CREATE DATABASE {database}", "postgres")
    report = {"status": "failed", "database": database, "identity": identity}
    process = None
    try:
        with (run / "backend.log").open("w", encoding="utf-8") as log, patch("publisher.requests", base.HTTP):
            process = start_server(log, database)
            migrations = sql("SELECT string_agg(version, ',' ORDER BY installed_rank) FROM flyway_schema_history WHERE success", database)
            assert migrations.split(",") == [f"1.{number}" for number in range(1, 12)], migrations
            publisher = Publisher(store, BASE, base.KEY)
            publisher.publish()
            first = receipt_identities(store)
            objects_before = base.objects()
            fields = store.view()["tracks"][0]["fields"]
            performer = fields["performers"][0]
            display = " / ".join(value.strip() for value in [performer["character"], performer["voice_actor"]] if value.strip())
            profiles = api("GET", "/admin/artist", params={"query": display})
            profile = next(row for row in profiles if row["name"] == display)
            assert profile["characterName"] == performer["character"]
            assert profile["voiceActorName"] == performer["voice_actor"]
            alias = "Verifier-" + run.name
            saved = api("PUT", f"/admin/artist/{profile['id']}/aliases", json={"aliases": [alias, "検証別名-" + run.name]})
            assert alias in saved["aliases"]
            # Match the same songs through another role too: EXISTS must not duplicate them.
            composer_name = fields["composer"][0]
            composer = next(row for row in api("GET", "/admin/artist", params={"query": composer_name}) if row["name"] == composer_name)
            old_composer_aliases = composer["aliases"]
            api("PUT", f"/admin/artist/{composer['id']}/aliases", json={"aliases": [*old_composer_aliases, alias]})
            expected_ids = {first[key]["songId"] for key in ["255", "256"]}
            search = api("GET", "/user/search", params={"query": alias})
            ids = [song["id"] for song in search["songs"]]
            assert set(ids) == expected_ids and len(ids) == len(set(ids)), search
            assert len([album for album in search["albums"] if album["id"] == first["album"]["albumId"]]) == 1
            for query in [performer["character"], performer["voice_actor"], composer_name, fields["title"],
                          store.view()["album"]["fields"]["title"], "検証別名-" + run.name]:
                matches = api("GET", "/user/search", params={"query": query})
                assert expected_ids <= {song["id"] for song in matches["songs"]}, (query, matches)
            # An uncredited BGM record must not match merely because it shares this album.
            album_id = first["album"]["albumId"]
            sql("INSERT INTO song (title, album_id, image_path, audio_path, display_order, music_kind, play_count) "
                f"SELECT 'Unrelated verification BGM', album_id, image_path, audio_path, 99, 'bgm', 0 FROM song WHERE id={min(expected_ids)}", database)
            isolated_matches = api("GET", "/user/search", params={"query": alias})
            assert {song["id"] for song in isolated_matches["songs"]} == expected_ids
            publisher.publish()
            assert receipt_identities(store) == first, "Retry changed catalog IDs or revisions"
            assert all(item["status"] == "unchanged" for item in store.read()["publication"]["attempt"]["records"])
            assert sql("SELECT count(*) FROM song", database) == "3", "Retry duplicated songs"
            assert sql("SELECT count(*) FROM album", database) == "1", "Retry duplicated albums"
            assert alias in api("GET", f"/admin/artist/{profile['id']}")["aliases"]
            assert base.objects() == objects_before, "Credit edits/retry changed media"
            assert {str(path): digest(source / path) for path in [Path("reviews.sqlite3"), *files]} == source_hashes
            unauthorized = base.HTTP.put(BASE + f"/admin/artist/{profile['id']}/aliases", json={"aliases": []}, timeout=10)
            assert unauthorized.status_code in {401, 403}
            report.update(status="passed", album_id=first["album"]["albumId"], song_ids=sorted(expected_ids),
                          profile=saved, search=search, migrations=migrations,
                          source_unchanged=True, checks=["structured character and voice actor", "manual aliases searchable",
                          "vocal and associated instrumental matches", "duplicate-role matches return songs once",
                          "alias edits and identical reimport preserve revisions/media", "unauthenticated alias edit rejected"])
    except Exception as error:
        report["error"] = str(error)
        raise
    finally:
        try:
            if process is not None:
                base.stop_server(process)
        finally:
            (run / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print("Evidence:", run)
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    verify(parser.parse_args().review.resolve())
