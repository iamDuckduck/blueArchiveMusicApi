"""Run with `python app.py`, then open http://127.0.0.1:8765."""

import argparse
import logging
import os
from pathlib import Path

from flask import Flask, abort, g, jsonify, render_template, request, send_file
from werkzeug.local import LocalProxy

from service import ReviewService
from store import Store, find_track
from publisher import Publisher
from catalog import Catalog


def create_app(data_dir=None, backend_url="http://127.0.0.1:8080", api_key=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    store = Store(data_dir or Path(__file__).parent / "data")
    publisher = Publisher(store, backend_url, api_key) if api_key else None
    service = ReviewService(store, publisher)
    catalog = Catalog(store.directory, service.job_lock)
    app.extensions["review_store"] = store
    app.extensions["review_service"] = service
    app.extensions["catalog"] = catalog
    reviews = {"veritas-vol-2": (store, publisher, service)}
    default_review = reviews["veritas-vol-2"]
    store = LocalProxy(lambda: g.review[0])
    publisher = LocalProxy(lambda: g.review[1])
    service = LocalProxy(lambda: g.review[2])

    def current_view():
        state = store.view()
        state["publication"]["enabled"] = g.review[1] is not None
        if g.review[1] is not None:
            state["publication"]["destination"] = g.review[1].backend_url
        prefix = g.review_prefix
        if state["album"]["cover"].get("preview_url"):
            state["album"]["cover"]["preview_url"] = prefix + state["album"]["cover"]["preview_url"]
        for track in state["tracks"]:
            if track["media"].get("preview_url"):
                track["media"]["preview_url"] = prefix + track["media"]["preview_url"]
        return state

    @app.before_request
    def local_requests_only():
        if request.host.split(":", 1)[0] not in {"127.0.0.1", "localhost"}:
            abort(403)
        if request.method in {"POST", "PUT", "DELETE"}:
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                abort(403)
            if not request.is_json:
                abort(415)
        identity = (request.view_args or {}).pop("album_id", None)
        g.review_prefix = f"/albums/{identity}" if identity else ""
        if identity and identity not in reviews:
            if catalog.job_lock.locked():
                raise ValueError("Wait for the local job to finish before opening another review.")
            new_store = catalog.open_review(identity)
            new_publisher = Publisher(new_store, backend_url, api_key) if api_key else None
            new_service = ReviewService(new_store, new_publisher)
            new_service.job_lock = catalog.job_lock
            reviews[identity] = (new_store, new_publisher, new_service)
        g.review = reviews[identity] if identity else default_review

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; media-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(ValueError)
    def invalid_input(error):
        return jsonify(error=str(error)), 400

    @app.get("/")
    def index():
        if g.review_prefix:
            catalog.sync_review(store)
        return render_template("index.html", review_prefix=g.review_prefix)

    @app.get("/catalog")
    def catalog_page():
        return render_template("catalog.html")

    @app.get("/api/catalog")
    def candidates():
        return jsonify(catalog.view())

    @app.get("/api/catalog/<identity>")
    def candidate(identity):
        item = catalog.read()["candidates"].get(identity)
        if item is None:
            abort(404)
        return jsonify(item)

    @app.post("/api/catalog/scan")
    def scan_catalog():
        catalog.start_scan()
        return jsonify(catalog.view()), 202

    @app.post("/api/catalog/<identity>/decision")
    def candidate_decision(identity):
        payload = request.get_json()
        if not isinstance(payload, dict):
            raise ValueError("Expected a candidate decision.")
        catalog.decide(identity, payload.get("decision"))
        if identity in reviews:
            decision = payload["decision"]
            reviews[identity][0].update(lambda s: s["album"].update(decision="skipped" if decision == "grouping" else decision))
        return jsonify(catalog.view())

    @app.post("/api/catalog/releases")
    def create_release():
        payload = request.get_json()
        if not isinstance(payload, dict):
            raise ValueError("Expected release fields.")
        catalog.create_release(payload)
        return jsonify(catalog.view())

    @app.post("/api/catalog/<identity>/map")
    def map_source_tracks(identity):
        payload = request.get_json()
        if not isinstance(payload, dict):
            raise ValueError("Expected target release and source tracks.")
        catalog.map_tracks(identity, payload.get("target"), payload.get("track_ids"))
        return jsonify(catalog.view())

    @app.post("/api/catalog/<identity>/link")
    def link_source_release(identity):
        payload = request.get_json()
        if not isinstance(payload, dict):
            raise ValueError("Expected a target release.")
        catalog.link_release(identity, payload.get("target"))
        return jsonify(catalog.view())

    @app.get("/api/review")
    def review():
        return jsonify(current_view())

    @app.put("/api/review")
    def save():
        if store.read()["job"].get("running"):
            raise ValueError("Wait for the local job to finish before changing review fields.")
        payload = request.get_json()
        if not isinstance(payload, dict):
            raise ValueError("Expected review fields.")
        store.save_edits(payload)
        return jsonify(current_view())

    @app.post("/api/decision")
    def decide():
        if store.read()["job"].get("running"):
            raise ValueError("Wait for preparation to finish before changing inclusion.")
        payload = request.get_json()
        decision = payload.get("decision") if isinstance(payload, dict) else None
        if decision not in {"review", "included", "skipped"}:
            raise ValueError("Choose review, included or skipped.")
        identity = store.read()["album"]["id"]
        if identity in catalog.read()["candidates"]:
            catalog.decide(identity, decision)
        store.update(lambda s: s["album"].update(decision=decision))
        return jsonify(current_view())

    @app.post("/api/tracks/<track_id>/inclusion")
    def include_track(track_id):
        if track_id not in {t["id"] for t in store.read()["tracks"] if t["source_id"] is not None}:
            abort(404)
        if store.read()["job"].get("running"):
            raise ValueError("Wait for preparation to finish before changing inclusion.")
        payload = request.get_json()
        included = payload.get("included") if isinstance(payload, dict) else None
        if type(included) is not bool:
            raise ValueError("Expected an inclusion choice.")
        track = find_track(store.read(), track_id)
        if included and (track["suggestions"] | track["edits"])["kind"] == "drama":
            raise ValueError("Spoken drama is excluded. Correct its music type first if it was misclassified.")
        store.update(lambda s: find_track(s, track_id).update(included=included))
        return jsonify(current_view())

    @app.post("/api/tracks/<track_id>/publication")
    def select_publication(track_id):
        if store.read()["job"].get("running"):
            raise ValueError("Wait for the local job to finish before changing publication selection.")
        track = next((t for t in store.read()["tracks"] if t["id"] == track_id), None)
        if track is None or track["source_id"] is None:
            abort(404)
        payload = request.get_json()
        selected = payload.get("selected") if isinstance(payload, dict) else None
        if type(selected) is not bool:
            raise ValueError("Expected a publication selection.")
        if selected and (not track["included"] or track["media"]["status"] != "ready"
                         or (track["suggestions"] | track["edits"])["kind"] == "drama"):
            raise ValueError("Select only included, prepared music for publication.")
        store.update(lambda s: find_track(s, track_id).update(publish_selected=selected))
        return jsonify(current_view())

    @app.post("/api/jobs/<action>")
    def job(action):
        service.start(action)
        return jsonify(current_view()), 202

    @app.post("/api/publication/baseline")
    def accept_publication_baseline():
        if g.review[1] is None:
            raise ValueError("Publication is not configured.")
        if store.read()["job"].get("running"):
            raise ValueError("Wait for the local job to finish.")
        payload = request.get_json()
        if not isinstance(payload, dict) or not isinstance(payload.get("record"), str):
            raise ValueError("Choose the published record to reconcile.")
        g.review[1].accept_baseline(payload["record"], payload.get("revision"))
        return jsonify(current_view())

    @app.post("/api/tracks/<track_id>/suggestions")
    def review_source_suggestions(track_id):
        if store.read()["job"].get("running"):
            raise ValueError("Wait for the local job to finish.")
        if track_id not in {t["id"] for t in store.read()["tracks"] if t["source_id"] is not None}:
            abort(404)
        payload = request.get_json()
        if not isinstance(payload, dict):
            raise ValueError("Choose incoming suggestions to review.")
        store.review_suggestions(track_id, payload.get("proposals"), payload.get("choice"))
        return jsonify(current_view())

    def local_media(relative):
        target = (store.directory / relative).resolve()
        media_root = (store.directory / "media").resolve()
        if not target.is_relative_to(media_root) or not target.is_file():
            abort(404)
        return send_file(target, conditional=True)

    @app.get("/media/audio/<track_id>")
    def audio(track_id):
        if track_id not in {t["id"] for t in store.read()["tracks"] if t["source_id"] is not None}:
            abort(404)
        item = find_track(store.read(), track_id)["media"]
        if item["status"] != "ready" or not item.get("path"):
            abort(404)
        return local_media(item["path"])

    @app.get("/media/cover/<size>")
    def cover(size):
        item = store.read()["album"]["cover"]
        if size not in {"400", "800", "original"} or item["status"] != "ready" or size not in item.get("files", {}):
            abort(404)
        return local_media(item["files"][size]["path"])

    # Reuse the same review handlers with a URL-scoped album, so tabs cannot switch each other's draft.
    for rule in list(app.url_map.iter_rules()):
        if rule.rule == "/" or (rule.rule.startswith(("/api/", "/media/")) and not rule.rule.startswith("/api/catalog")):
            app.add_url_rule("/albums/<album_id>" + rule.rule, endpoint="album_" + rule.endpoint,
                             view_func=app.view_functions[rule.endpoint], methods=rule.methods - {"HEAD", "OPTIONS"})
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local album review with explicit publication to the configured backend. Verify the destination before publishing.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, help="Optional location for saved reviews and media")
    parser.add_argument("--backend-url", default=os.getenv("CATALOG_IMPORT_BACKEND_URL", "http://127.0.0.1:8080"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    create_app(args.data_dir, args.backend_url, os.getenv("CATALOG_IMPORT_API_KEY")).run(
        host="127.0.0.1", port=args.port, debug=False, use_reloader=False, threaded=True)
