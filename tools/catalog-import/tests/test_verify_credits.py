"""The next-stage verifier cannot select the development or pipeline-test DB."""

import unittest
from unittest.mock import Mock, patch

import verify_credits as verifier


class CreditsIsolationTests(unittest.TestCase):
    def test_arguments_keep_local_media_and_select_only_fresh_credits_database(self):
        args = verifier.server_arguments("java", "catalog_credits_verify_1234abcd")
        self.assertIn("--server.port=18084", args)
        self.assertIn("--server.address=127.0.0.1", args)
        for setting in ["spring.datasource.url", "spring.flyway.url"]:
            self.assertIn(f"--{setting}=jdbc:postgresql://127.0.0.1:15433/catalog_credits_verify_1234abcd", args)
        self.assertFalse(any("/catalog_import_verify" in arg for arg in args))
        self.assertTrue(any("127.0.0.1:19000" in arg for arg in args))

    def test_rejects_other_databases_before_process_or_sql(self):
        for database in ["blue_archive_api", "catalog_import_verify", "catalog_credits_verify", "catalog_credits_verify_1234abcd;DROP"]:
            with self.subTest(database=database), patch("verify_credits.subprocess.run") as run:
                with self.assertRaises(ValueError):
                    verifier.start_server(Mock(), database)
                with self.assertRaises(ValueError):
                    verifier.sql("SELECT 1", database)
                run.assert_not_called()

    def test_busy_port_never_reuses_or_stops_another_server(self):
        jar = Mock()
        jar.is_file.return_value = True
        with patch.object(verifier.base, "JAR", jar), patch("verify_credits.socket.socket") as socket, \
                patch("verify_credits.subprocess.Popen") as start, patch.object(verifier.base, "stop_server") as stop:
            socket.return_value.__enter__.return_value.connect_ex.return_value = 0
            with self.assertRaisesRegex(RuntimeError, "already in use"):
                verifier.start_server(Mock(), "catalog_credits_verify_1234abcd")
            start.assert_not_called()
            stop.assert_not_called()

    def test_receipt_comparison_ignores_created_vs_unchanged_status(self):
        store = Mock()
        receipt = {"songId": 8, "albumId": 7, "revision": "abc", "status": "created", "created": True}
        store.read.return_value = {"publication": {"destinations": {verifier.BASE: {"receipts": {"255": receipt}}}}}
        before = verifier.receipt_identities(store)
        receipt.update(status="unchanged", created=False)
        self.assertEqual(before, verifier.receipt_identities(store))


if __name__ == "__main__":
    unittest.main()
