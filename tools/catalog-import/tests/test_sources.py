"""Source-shape and evidence tests; no network or saved review changes."""

import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from sources import (content_text, cv_names, fetch_gamekee, fetch_kivo,
                     gamekee_evidence, kivo_media_url, suggestions_from_kivo)


def response(payload=None, status=200):
    result = Mock(status_code=status)
    result.json.return_value = payload
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status}")
    return result


def article(**changes):
    data = {"id": 691994, "title": "Reviewed reference", "game": {"alias": "ba"},
            "content": "<p>Composer: Nor</p>", "updated_at": 1781795943}
    data.update(changes)
    return {"code": 0, "data": data}


class KivoReaderTests(unittest.TestCase):
    def test_reviewed_veritas_fixtures_still_produce_four_cv_credits(self):
        for identity in (255, 256):
            with self.subTest(identity=identity):
                fixture = Path(__file__).parent / "fixtures" / f"kivo-{identity}.json"
                payload = json.loads(fixture.read_text(encoding="utf-8"))
                with patch("sources.requests.get", return_value=response(payload)) as get:
                    data = fetch_kivo(identity)
                self.assertEqual(data, payload["data"])
                self.assertFalse(get.call_args.kwargs["allow_redirects"])
                suggestions = suggestions_from_kivo(data)
                self.assertEqual(len(suggestions["performers"].splitlines()), 4)
                self.assertNotIn("composer", suggestions)

    def test_standalone_language_versions_do_not_invent_roles_or_numbers(self):
        # Minimal snapshots of live Kivo 197/198 checked on 2026-09-20. The KR
        # introduction also says English; the reader must not override its title.
        for identity, language in ((197, "EN"), (198, "KR")):
            with self.subTest(identity=identity):
                data = {"id": identity, "title": f"Thanks to ({language} Ver)",
                        "album": "Thanks to", "author": "Younha / Mitsukiyo",
                        "introduction": "国际服1.5周年贺曲英文版。暂未发布专辑或上线流媒体平台。",
                        "cover": "//static.kivo.wiki/images/cover.jpg",
                        "file": "//static.kivo.wiki/musics/Thanks%20to.mp3"}
                with patch("sources.requests.get", return_value=response({"success": True, "data": data})):
                    fetched = fetch_kivo(identity)
                self.assertEqual(suggestions_from_kivo(fetched), {"title": data["title"]})

    def test_invalid_input_ids_do_not_make_requests(self):
        for identity in (True, 0, -1, "197", None):
            with self.subTest(identity=identity), patch("sources.requests.get") as get:
                with self.assertRaises(ValueError):
                    fetch_kivo(identity)
                get.assert_not_called()

    def test_malformed_payloads_are_reported_as_source_errors(self):
        valid = {"id": 197, "title": "Thanks to"}
        bad_payloads = [None, [], {}, {"success": True, "data": []},
                        {"success": False, "data": valid},
                        {"success": True, "data": valid | {"id": 198}},
                        {"success": True, "data": valid | {"id": True}},
                        *({"success": True, "data": valid | {"title": value}} for value in (None, " ", [])),
                        *({"success": True, "data": valid | {field: []}}
                          for field in ("introduction", "author", "album", "cover", "file"))]
        for payload in bad_payloads:
            with self.subTest(payload=payload), patch("sources.requests.get", return_value=response(payload)):
                with self.assertRaises(ValueError):
                    fetch_kivo(197)

    def test_missing_optional_details_are_allowed_and_not_guessed(self):
        data = {"id": 197, "title": "Known track", "introduction": None, "file": None}
        with patch("sources.requests.get", return_value=response({"success": True, "data": data})):
            self.assertEqual(fetch_kivo(197), data)
        self.assertEqual(suggestions_from_kivo(data), {"title": "Known track"})

    def test_explicit_composer_lines_are_deduplicated_but_combined_roles_are_not_guessed(self):
        data = {"title": "Track", "author": "Generic person",
                "introduction": "<p>Composer: Nor</p><p>作曲：Mitsukiyo</p><p>Composer: Nor</p>"
                                "<p>作词/作曲: Ambiguous</p><p>Arrangement: Arranger</p>"}
        self.assertEqual(suggestions_from_kivo(data), {"title": "Track", "composer": "Nor\nMitsukiyo"})

    def test_empty_composer_label_does_not_capture_the_next_line(self):
        self.assertEqual(suggestions_from_kivo({"title": "Track", "introduction": "Composer:\nUnlabelled person"}),
                         {"title": "Track"})
        self.assertEqual(suggestions_from_kivo({"title": "Track", "introduction": "<p>Composer: Nor</p>Other evidence"}),
                         {"title": "Track", "composer": "Nor"})

    def test_redirects_and_http_errors_are_not_successful_records(self):
        for status in (302, 403, 404, 567):
            with self.subTest(status=status), patch("sources.requests.get", return_value=response(status=status)):
                with self.assertRaises((ValueError, requests.HTTPError)):
                    fetch_kivo(197)

    def test_media_urls_stay_on_the_public_kivo_https_host(self):
        self.assertEqual(kivo_media_url("//static.kivo.wiki/a.mp3"), "https://static.kivo.wiki/a.mp3")
        for url in (None, 1, "http://static.kivo.wiki/a.mp3", "https://elsewhere.test/a.mp3",
                    "https://user@static.kivo.wiki/a.mp3", "https://static.kivo.wiki:8080/a.mp3"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                kivo_media_url(url)


class GameKeeReaderTests(unittest.TestCase):
    def test_missing_reference_is_not_a_remote_failure(self):
        with patch("sources.requests.get") as get:
            result = fetch_gamekee("")
        get.assert_not_called()
        self.assertEqual(result["status"], "missing_reference")
        self.assertEqual(result["text"], "")
        self.assertIn("No GameKee reference", result["error"])

    def test_invalid_reference_does_not_send_requests(self):
        for url in (None, 2, "http://www.gamekee.com/ba/691994.html",
                    "https://other.test/ba/691994.html", "https://www.gamekee.com/other/691994.html",
                    "https://www.gamekee.com/ba/0.html", "https://user@www.gamekee.com/ba/691994.html"):
            with self.subTest(url=url), patch("sources.requests.get") as get:
                result = fetch_gamekee(url)
                get.assert_not_called()
                self.assertEqual(result["status"], "failed")

    def test_direct_article_contains_review_only_evidence(self):
        html = "<table><tr><td>作曲</td><td>Nor</td></tr><tr><td>发行日期</td><td>2023年12月25日</td></tr></table>"
        with patch("sources.requests.get", return_value=response(article(content=html))) as get:
            result = fetch_gamekee()
        self.assertEqual(get.call_count, 1)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["article"], {"id": 691994, "title": "Reviewed reference", "updated_at": 1781795943})
        self.assertEqual(result["evidence"]["credits"], [{"role": "composer", "value": "Nor", "line": "作曲\tNor"}])
        self.assertEqual(result["evidence"]["release_dates"][0]["value"], "2023年12月25日")
        self.assertNotIn("suggestions", result)

    def test_content_cdn_json_is_read_without_redirects(self):
        api = article(content="", content_cdn="//api-cdn.gamekee.com/wiki2.0/pro/829/content/691994.json?v=1")
        document = {"content_json": json.dumps({"ops": [{"insert": "Composer: Nor\n"}]})}
        with patch("sources.requests.get", side_effect=[response(api), response(document)]) as get:
            result = fetch_gamekee()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["text"], "Composer: Nor")
        self.assertEqual(result["content_raw"], document)
        self.assertTrue(all(call.kwargs["allow_redirects"] is False for call in get.call_args_list))

    def test_cdn_security_failure_retains_only_labelled_partial_summary(self):
        api = article(content="", content_cdn="//api-cdn.gamekee.com/content.json",
                      summary="作词/作曲Norタ野ヨシミ发行日期2023年12月25日")
        with patch("sources.requests.get", side_effect=[response(api), response(status=567)]):
            result = fetch_gamekee()
        self.assertEqual(result["status"], "failed")
        self.assertIn("567", result["error"])
        self.assertEqual(result["text"], "")
        self.assertEqual(result["article"]["id"], 691994)
        self.assertEqual(result["summary"], api["data"]["summary"])
        self.assertNotIn("evidence", result)

    def test_summary_alone_does_not_claim_full_article_success(self):
        with patch("sources.requests.get", return_value=response(article(content="", summary="Some credits"))):
            result = fetch_gamekee()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["summary"], "Some credits")
        self.assertNotIn("evidence", result)

    def test_unexpected_cdn_host_userinfo_and_port_are_not_requested(self):
        for url in ("https://other.test/content.json", "http://api-cdn.gamekee.com/content.json",
                    "https://user@api-cdn.gamekee.com/content.json", "https://api-cdn.gamekee.com:8080/content.json"):
            with self.subTest(url=url), patch("sources.requests.get", return_value=response(article(content="", content_cdn=url))) as get:
                result = fetch_gamekee()
                self.assertEqual(get.call_count, 1)
                self.assertEqual(result["status"], "failed")

    def test_wrong_article_and_non_article_payloads_are_rejected(self):
        for payload in (None, [], {"code": False, "data": {}}, article(id=1), article(id="691994"),
                        article(title=""), article(game={"alias": "other"}), article(game=["ba"])):
            with self.subTest(payload=payload), patch("sources.requests.get", return_value=response(payload)):
                result = fetch_gamekee()
                self.assertEqual(result["status"], "failed")
                self.assertNotIn("evidence", result)

    def test_invalid_json_and_redirects_remain_visible_failures(self):
        invalid = response()
        invalid.json.side_effect = ValueError("Invalid JSON")
        for remote in (invalid, response(status=302), response(status=403)):
            with self.subTest(remote=remote), patch("sources.requests.get", return_value=remote):
                self.assertEqual(fetch_gamekee()["status"], "failed")

    def test_large_content_is_explicitly_marked_truncated(self):
        with patch("sources.requests.get", return_value=response(article(content="x" * 80001))):
            result = fetch_gamekee()
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["text"]), 80000)


class ArticleEvidenceTests(unittest.TestCase):
    def test_json_editor_text_and_html_scripts(self):
        self.assertEqual(content_text({"content": [{"type": "paragraph", "content": [{"text": "Composer: Nor"}]}]}),
                         "Composer: Nor")
        self.assertEqual(content_text('<p>Artist: A &amp; B</p><script>bad()</script><style>hidden</style>'),
                         "Artist: A & B")
        self.assertEqual(content_text({"unrelated": "Not an article"}), "")

    def test_ambiguous_labels_generic_authors_and_lyrics_are_not_assigned(self):
        evidence = gamekee_evidence("作词/作曲: A / B\nAuthor: Generic\nLyrics: Writer\nArranger: Arranger")
        self.assertEqual(evidence, {"credits": [], "performers": "", "release_dates": []})

    def test_explicit_roles_keep_the_original_line(self):
        evidence = gamekee_evidence("Vocal: Younha\n作曲：Mitsukiyo\nRelease date: not verified")
        self.assertEqual(evidence["credits"], [
            {"role": "artist", "value": "Younha", "line": "Vocal: Younha"},
            {"role": "composer", "value": "Mitsukiyo", "line": "作曲：Mitsukiyo"},
        ])
        self.assertEqual(evidence["release_dates"], [{"value": "not verified", "line": "Release date: not verified"}])

    def test_translated_cv_blocks_do_not_duplicate_performers(self):
        text = "Group《A(CV: Actor)、B（CV：Other）》\nGroup《Translated A(CV: Actor)、Translated B(CV: Other)》"
        self.assertEqual(cv_names(text), "A (CV: Actor)\nB (CV: Other)")
        self.assertEqual(gamekee_evidence(text)["performers"], cv_names(text))
        self.assertEqual(cv_names(None), "")


if __name__ == "__main__":
    unittest.main()
