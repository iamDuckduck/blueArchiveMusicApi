"""Run with `python app.py`, then open http://127.0.0.1:8765."""

import argparse
import logging
import os
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

from service import ReviewService
from store import Store, find_track
from publisher import Publisher


def create_app(data_dir=None, backend_url="http://127.0.0.1:8080", api_key=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    store = Store(data_dir or Path(__file__).parent / "data")
    publisher = Publisher(store, backend_url, api_key) if api_key else None
    service = ReviewService(store, publisher)
    app.extensions["review_store"] = store
    app.extensions["review_service"] = service

    def current_view():
        state = store.view()
        state["publication"]["enabled"] = publisher is not None
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
        return render_template("index.html")

    @app.get("/api/review")
    def review():
        return jsonify(current_view())

    @app.put("/api/review")
    def save():
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
        store.update(lambda s: s["album"].update(decision=decision))
        return jsonify(current_view())

    @app.post("/api/tracks/<track_id>/inclusion")
    def include_track(track_id):
        if track_id not in {"255", "256"}:
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

    def local_media(relative):
        target = (store.directory / relative).resolve()
        media_root = (store.directory / "media").resolve()
        if not target.is_relative_to(media_root) or not target.is_file():
            abort(404)
        return send_file(target, conditional=True)

    @app.get("/media/audio/<track_id>")
    def audio(track_id):
        if track_id not in {"255", "256"}:
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
