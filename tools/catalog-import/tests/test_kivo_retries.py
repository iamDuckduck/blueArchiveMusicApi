"""Bounded source retries never retry writes or replace an incomplete catalog."""
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests
from catalog import Catalog, fetch_index
from sources import kivo_response


def page(identity, pages=2):
    return Mock(status_code=200, json=lambda: {
        "success": True, "data": {"max_page": pages,
        "music": [{"id": identity, "title": "Music", "album": "Album"}]}})


class RetryTests(unittest.TestCase):
    @patch("sources.time.sleep")
    def test_retry_same_page_without_duplicate_records(self, sleep):
        messages = []
        with patch("sources.requests.get", side_effect=[page(1), requests.ReadTimeout(), page(2)]) as get:
            rows = fetch_index(messages.append)
        self.assertEqual([r["id"] for r in rows], [1, 2])
        self.assertEqual([c.kwargs["params"]["page"] for c in get.call_args_list], [1, 2, 2])
        self.assertTrue(any("Retrying (2/3)" in m for m in messages))
        sleep.assert_called_once_with(1)

    @patch("sources.time.sleep")
    def test_exhausted_scan_keeps_existing_candidates(self, sleep):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Catalog(directory)
            catalog.merge([{"id": 9, "title": "Saved", "album": "Saved album"}])
            before = catalog.read()["candidates"]
            with patch("sources.requests.get", side_effect=requests.ReadTimeout()) as get:
                catalog.start_scan()
                catalog.thread.join(5)
            self.assertFalse(catalog.thread.is_alive())
            self.assertEqual(get.call_count, 3)
            self.assertEqual(catalog.read()["candidates"], before)
            self.assertIn("after 3 attempts", catalog.read()["scan"]["message"])

    @patch("sources.time.sleep")
    def test_transient_gateway_error_retries_and_closes_response(self, sleep):
        failed, success = Mock(status_code=503), page(1)
        with patch("sources.requests.get", side_effect=[failed, success]):
            self.assertIs(kivo_response("https://api.kivo.wiki/api/v1/musics/255"), success)
        failed.close.assert_called_once()

    @patch("sources.time.sleep")
    def test_certificate_and_permanent_http_errors_do_not_retry(self, sleep):
        for error in [requests.exceptions.SSLError(), requests.HTTPError()]:
            with self.subTest(error=type(error)), patch("sources.requests.get", side_effect=error) as get:
                with self.assertRaises((ValueError, requests.HTTPError)):
                    kivo_response("https://api.kivo.wiki/api/v1/musics/255")
                self.assertEqual(get.call_count, 1)
        sleep.assert_not_called()
