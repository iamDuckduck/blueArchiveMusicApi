"""Verifier safety checks use temporary fixtures, never Docker, Java, or live media."""

import hashlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from store import Store, find_track
import verify_live as verifier


class PreparedReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.store = Store(self.source)

        def file_item(relative):
            destination = self.source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"unit-test media: " + relative.encode())
            return {"status": "ready", "path": relative, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}

        covers = {key: file_item(f"media/cover/{key}.jpg") for key in ["original", "400", "800"]}
        audio = {identity: file_item(f"media/{identity}/audio.mp3") for identity in [255, 256]}

        def prepare(state):
            state["album"].update(decision="included", cover={"status": "ready", "files": covers})
            for identity in [255, 256]:
                find_track(state, identity).update(media=audio[identity], publish_selected=True)

        self.store.update(prepare)

    def test_copies_only_validated_references_and_preserves_source_bytes(self):
        unused = self.source / "media" / "unused-demo.mp3"
        unused.write_bytes(b"must not be copied")
        before = self.store.database.read_bytes()
        review = verifier.create_review_copy(self.source, self.root / "run")
        self.assertEqual(self.store.database.read_bytes(), before)
        self.assertFalse((review / "media" / unused.name).exists())
        self.assertEqual(len(list((review / "media").rglob("*.*"))), 5)
        self.assertEqual(Store(review).view()["album"]["id"], "veritas-vol-2")

    def assert_rejected_without_run(self, message):
        run = self.root / "run"
        before = self.store.database.read_bytes()
        with self.assertRaisesRegex(ValueError, message):
            verifier.create_review_copy(self.source, run)
        self.assertFalse(run.exists())
        self.assertEqual(self.store.database.read_bytes(), before)

    def test_rejects_demo_or_unapproved_album_before_copy(self):
        self.store.update(lambda state: state["album"].update(id="demo-release"))
        self.assert_rejected_without_run("reviewed Veritas")
        self.store.update(lambda state: state["album"].update(id="veritas-vol-2", decision="review"))
        self.assert_rejected_without_run("reviewed Veritas")

    def test_rejects_incomplete_selection_and_pending_proposals(self):
        self.store.update(lambda state: find_track(state, 256).update(publish_selected=False))
        self.assert_rejected_without_run("select exactly")
        self.store.update(lambda state: find_track(state, 256).update(publish_selected=True,
                         pending_suggestions={"kivo": {"title": "Unreviewed title"}}))
        self.assert_rejected_without_run("incoming source")

    def test_rejects_unprepared_and_changed_media(self):
        self.store.update(lambda state: find_track(state, 256)["media"].update(status="pending"))
        self.assert_rejected_without_run("Prepare both")
        self.store.update(lambda state: find_track(state, 256)["media"].update(status="ready", sha256="invalid"))
        self.assert_rejected_without_run("validation hash")

    def test_rejects_outside_media_even_with_a_valid_hash(self):
        outside = self.root / "outside.mp3"
        outside.write_bytes(b"outside")
        self.store.update(lambda state: find_track(state, 255)["media"].update(
            path="../outside.mp3", sha256=hashlib.sha256(b"outside").hexdigest()))
        self.assert_rejected_without_run("outside this review")

    def test_missing_review_is_not_silently_initialized(self):
        missing = self.root / "missing"
        with self.assertRaisesRegex(ValueError, "prepared Veritas"):
            verifier.create_review_copy(missing, self.root / "run")
        self.assertFalse(missing.exists())
        self.assertFalse((self.root / "run").exists())

    def test_inside_source_traversal_alias_is_normalized_before_copy(self):
        self.store.update(lambda state: find_track(state, 255)["media"].update(
            path="../source/media/255/audio.mp3"))
        before = self.store.database.read_bytes()
        run = self.root / "run"
        review = verifier.create_review_copy(self.source, run)
        self.assertTrue((review / "media" / "255" / "audio.mp3").is_file())
        self.assertFalse((run / "source").exists())
        self.assertEqual(find_track(Store(review).read(), 255)["media"]["path"], "media/255/audio.mp3")
        self.assertEqual(self.store.database.read_bytes(), before)


class FixedEnvironmentTests(unittest.TestCase):
    def test_poisoned_environment_cannot_override_destinations_or_java_options(self):
        poisoned = {
            "PATH": "test-path", "SystemRoot": "test-system", "TEMP": "test-temp",
            "SPRING_APPLICATION_JSON": '{"spring":{"datasource":{"url":"production"}}}',
            "SPRING_CONFIG_LOCATION": "production.yaml", "SPRING_PROFILES_ACTIVE": "prod",
            "SPRING_DATASOURCE_URL": "jdbc:postgresql://production/catalog",
            "BLUEARCHIVE_R2_ENDPOINT": "https://production", "CLOUDFLARE_R2_BUCKET": "production",
            "R2_BUCKET": "production", "AWS_PROFILE": "production", "POSTGRES_DB": "production",
            "DOCKER_HOST": "tcp://remote:2375", "DOCKER_CONTEXT": "production",
            "JAVA_TOOL_OPTIONS": "-Dspring.profiles.active=prod", "JDK_JAVA_OPTIONS": "-javaagent:unexpected.jar",
            "_JAVA_OPTIONS": "-Dserver.port=8080", "HTTP_PROXY": "http://proxy", "CATALOG_IMPORT_API_KEY": "real-key",
        }
        with patch.dict(os.environ, poisoned, clear=True):
            environment = verifier.local_environment()
            command = verifier.server_arguments(Path("java"))
        self.assertEqual({key.upper() for key in environment}, {"PATH", "SYSTEMROOT", "TEMP"})
        self.assertIn("--spring.profiles.active=catalog-verify", command)
        self.assertIn("--spring.docker.compose.enabled=false", command)
        self.assertIn("--spring.datasource.url=jdbc:postgresql://127.0.0.1:15433/catalog_import_verify", command)
        self.assertIn("--cloudflare.r2.endpoint=http://127.0.0.1:19000", command)
        self.assertIn("--cloudflare.r2.bucket=catalog-import-verify", command)
        self.assertIn("--spring.flyway.baseline-on-migrate=false", command)
        self.assertIn("--spring.jpa.hibernate.ddl-auto=none", command)
        self.assertFalse(verifier.HTTP.trust_env)
        self.assertNotIn("production", " ".join(command))
        self.assertNotIn("--spring.profiles.active=catalog-import", command)

    def test_docker_reads_pin_local_engine_and_named_test_containers(self):
        result = Mock(stdout="[]")
        with patch("verify_live.subprocess.run", return_value=result) as run:
            verifier.sql("SELECT 1")
            result.stdout = ""
            self.assertEqual(verifier.objects(), {})
        for call in run.call_args_list:
            self.assertEqual(call.args[0][:3], verifier.DOCKER)
            self.assertIn("--host", call.args[0])
            self.assertNotIn("DOCKER_HOST", call.kwargs["env"])
        self.assertIn("catalog-import-verify-postgres-1", run.call_args_list[0].args[0])
        self.assertIn("verify/catalog-import-verify", run.call_args_list[1].args[0])

    def test_missing_jar_stops_before_network_or_source_copy(self):
        with patch("verify_live.JAR", Path("missing-backend-verifier.jar")), \
                patch("verify_live.create_review_copy") as copy, patch("verify_live.start_server") as start:
            with self.assertRaisesRegex(RuntimeError, "Build the backend jar"):
                verifier.verify(Path("missing-review"))
        copy.assert_not_called()
        start.assert_not_called()


class ServerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.jar = Mock()
        self.jar.is_file.return_value = True
        self.probe = Mock()
        self.probe.connect_ex.return_value = 1
        self.socket = Mock()
        self.socket.__enter__ = Mock(return_value=self.probe)
        self.socket.__exit__ = Mock(return_value=False)
        self.process = Mock()
        self.process.poll.return_value = None
        self.settings = Mock(stderr="    java.home = C:/verified-jdk\n")
        self.addCleanup(patch.stopall)
        patch("verify_live.JAR", self.jar).start()
        patch("verify_live.socket.socket", return_value=self.socket).start()
        self.run = patch("verify_live.subprocess.run", return_value=self.settings).start()
        self.popen = patch("verify_live.subprocess.Popen", return_value=self.process).start()
        patch("verify_live.time.sleep").start()

    def test_busy_port_refuses_to_reuse_unknown_server(self):
        self.probe.connect_ex.return_value = 0
        with self.assertRaisesRegex(RuntimeError, "already in use"):
            verifier.start_server(io.StringIO())
        self.run.assert_not_called()
        self.popen.assert_not_called()

    def test_server_is_started_with_fixed_arguments_and_sanitized_environment(self):
        with patch.dict(os.environ, {"JAVA_TOOL_OPTIONS": "unsafe", "SPRING_PROFILES_ACTIVE": "prod"}), \
                patch.object(verifier.HTTP, "get", return_value=Mock(status_code=200)) as get:
            self.assertIs(verifier.start_server(io.StringIO()), self.process)
        command = self.popen.call_args.args[0]
        self.assertIn("--server.address=127.0.0.1", command)
        self.assertIn("--server.port=18082", command)
        self.assertIn("--spring.docker.compose.enabled=false", command)
        self.assertNotIn("JAVA_TOOL_OPTIONS", self.popen.call_args.kwargs["env"])
        self.assertNotIn("SPRING_PROFILES_ACTIVE", self.run.call_args.kwargs["env"])
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_readiness_timeout_stops_child_process(self):
        with patch.object(verifier.HTTP, "get", return_value=Mock(status_code=503)):
            with self.assertRaisesRegex(RuntimeError, "did not become ready"):
                verifier.start_server(io.StringIO())
        self.process.terminate.assert_called_once()
        self.process.wait.assert_called_once_with(timeout=10)

    def test_stop_kills_only_its_child_if_termination_times_out(self):
        self.process.wait.side_effect = [subprocess.TimeoutExpired("java", 10), None]
        verifier.stop_server(self.process)
        self.process.terminate.assert_called_once()
        self.process.kill.assert_called_once()
        self.assertEqual(self.process.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()
