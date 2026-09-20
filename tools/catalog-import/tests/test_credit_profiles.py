import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from creditprofiles import CreditProfiles
from app import create_app


def profile(identity=12):
    return {"id": identity, "name": "Younha", "characterName": None,
            "voiceActorName": None, "aliases": ["ユンナ", "윤하"]}


class CreditProfileTests(unittest.TestCase):
    def setUp(self):
        self.profiles = CreditProfiles("http://127.0.0.1:18083/", "test-only-key")
        self.request = patch("creditprofiles.requests.request").start()
        self.addCleanup(patch.stopall)

    def response(self, payload, status=200):
        self.request.return_value = Mock(status_code=status, json=Mock(return_value=payload))

    def test_search_get_and_explicit_alias_update_use_configured_auth_without_redirects(self):
        self.response([profile()])
        self.assertEqual(self.profiles.search("  Younha  "), [profile()])
        self.request.assert_called_with("GET", "http://127.0.0.1:18083/admin/artist",
                                        headers={"X-Admin-Api-Key": "test-only-key"},
                                        timeout=(5, 20), allow_redirects=False, params={"query": "Younha"})
        self.response(profile())
        self.assertEqual(self.profiles.get(12), profile())
        self.assertEqual(self.request.call_args.args, ("GET", "http://127.0.0.1:18083/admin/artist/12"))
        self.profiles.save_aliases(12, [" 윤하 ", "ユンナ"])
        self.assertEqual(self.request.call_args.args, ("PUT", "http://127.0.0.1:18083/admin/artist/12/aliases"))
        self.assertEqual(self.request.call_args.kwargs["json"], {"aliases": ["윤하", "ユンナ"]})
        self.profiles.save_aliases(12, [])
        self.assertEqual(self.request.call_args.kwargs["json"], {"aliases": []})

    def test_profile_keeps_distinct_character_and_voice_actor_and_only_public_fields(self):
        record = profile() | {"characterName": "チヒロ", "voiceActorName": "山村響", "internal": "not for UI"}
        self.response(record)
        result = self.profiles.get(12)
        self.assertEqual(result["characterName"], "チヒロ")
        self.assertEqual(result["voiceActorName"], "山村響")
        self.assertNotIn("internal", result)

    def test_invalid_ids_aliases_and_queries_are_rejected_before_any_request(self):
        for identity in [None, True, "12", "../artist", -1, 0]:
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                self.profiles.get(identity)
        for aliases in [None, {}, "name", [""], [" "], [123], ["a\nb"], ["a" * 256], ["name"] * 21]:
            with self.subTest(aliases=aliases), self.assertRaises(ValueError):
                self.profiles.save_aliases(12, aliases)
        for query in [None, [], "x" * 256]:
            with self.subTest(query=query), self.assertRaises(ValueError):
                self.profiles.search(query)
        self.request.assert_not_called()

    def test_missing_key_and_unsafe_config_do_not_send_requests(self):
        with self.assertRaisesRegex(ValueError, "API key"):
            CreditProfiles("http://127.0.0.1:18083", None).search("")
        for url in ["file:///catalog", "https://key@example.com", "https://:key@example.com", "https://example.com?key=secret"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                CreditProfiles(url, "test-only-key")
        self.request.assert_not_called()

    def test_network_errors_do_not_expose_auth_or_claim_a_save_succeeded(self):
        self.request.side_effect = requests.ConnectionError("test-only-key in transport diagnostic")
        with self.assertRaises(ValueError) as caught:
            self.profiles.save_aliases(12, ["ユンナ"])
        self.assertNotIn("test-only-key", str(caught.exception))
        self.assertIn("not confirmed saved", str(caught.exception))

    def test_http_errors_invalid_json_wrong_ids_and_malformed_profiles_fail_clearly(self):
        for status in [302, 400, 401, 403, 404, 500]:
            self.response(profile(), status)
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.profiles.get(12)
        self.response(profile())
        self.request.return_value.json.side_effect = ValueError("not json")
        with self.assertRaisesRegex(ValueError, "invalid credit profile response"):
            self.profiles.get(12)
        for record in [None, {}, profile(13), profile() | {"aliases": "not a list"}, profile() | {"voiceActorName": []}]:
            self.response(record)
            with self.subTest(record=record), self.assertRaises(ValueError):
                self.profiles.get(12)
        self.response([profile()] * 51)
        with self.assertRaisesRegex(ValueError, "invalid credit search"):
            self.profiles.search("")

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed for the UI behavior check")
    def test_ui_only_saves_aliases_on_explicit_submit(self):
        script = Path(__file__).resolve().parents[1] / "static" / "credits.js"
        javascript = r"""
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const elements = new Map(), calls = [];
function make() {return {value:'', listeners:{}, addEventListener(name, fn) {this.listeners[name]=fn}, replaceChildren() {}, append() {}}}
function element(key) {if (!elements.has(key)) elements.set(key, make()); return elements.get(key)}
const saved = {id:12, name:'Younha', characterName:null, voiceActorName:null, aliases:['윤하']};
const context = vm.createContext({
  document:{body:{dataset:{creditsEnabled:'true'}}, querySelector:element, querySelectorAll:()=>[], createElement:make},
  window:{addEventListener() {}, confirm:()=>true},
  fetch:async (url, options) => {calls.push({url, options}); return {ok:true, json:async()=>({...saved, aliases:['ユンナ']})}},
  profile:saved
});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
assert.equal(calls.length, 0, 'opening the page does not fetch or mutate backend state');
vm.runInContext('showProfile(profile); controls()', context);
element('#credit-aliases').value = 'ユンナ';
element('#credit-aliases').listeners.input();
assert.equal(calls.length, 0, 'typing must not autosave to the backend');
assert.equal(element('#save-aliases').disabled, false);
(async () => {
  await element('#credit-editor').listeners.submit({preventDefault() {}});
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/api/credits/12/aliases');
  assert.equal(calls[0].options.method, 'PUT');
  assert.deepEqual(JSON.parse(calls[0].options.body), {aliases:['ユンナ']});
  assert.equal(calls[0].options.headers['X-Admin-Api-Key'], undefined, 'credentials never enter browser requests');
  assert.equal(element('#save-aliases').disabled, true);
  assert.equal(element('[data-profile-id="12"] small').textContent, 'Profile #12 · 1 aliases', 'result summary follows the saved profile');
})().catch(error => {console.error(error); process.exitCode = 1});
"""
        result = subprocess.run([shutil.which("node"), "-e", javascript, str(script)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class CreditProfileRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = create_app(self.temp.name, "http://127.0.0.1:18083", "test-only-key").test_client()
        self.request = patch("creditprofiles.requests.request").start()
        self.addCleanup(patch.stopall)
        self.request.return_value = Mock(status_code=200, json=Mock(return_value=profile()))

    def test_page_has_destination_but_not_credentials_and_shared_routes_are_not_album_scoped(self):
        page = self.client.get("/credits").get_data(as_text=True)
        self.assertIn("http://127.0.0.1:18083", page)
        self.assertIn("Save aliases to backend", page)
        self.assertNotIn("test-only-key", page)
        self.assertEqual(self.client.get("/albums/veritas-vol-2/api/credits").status_code, 404)
        self.request.assert_not_called()

    def test_search_profile_and_alias_routes_match_the_browser_contract(self):
        self.request.return_value.json.return_value = [profile()]
        response = self.client.get("/api/credits?query=Younha")
        self.assertEqual(response.json, {"profiles": [profile()]})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.request.return_value.json.return_value = profile()
        self.assertEqual(self.client.get("/api/credits/12").json, profile())
        response = self.client.put("/api/credits/12/aliases", json={"aliases": ["윤하"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["id"], 12)
        self.assertEqual(self.request.call_args.kwargs["json"], {"aliases": ["윤하"]})

    def test_foreign_write_missing_json_and_extra_profile_fields_cannot_reach_backend(self):
        self.assertEqual(self.client.put("/api/credits/12/aliases", json={"aliases": []},
                                         headers={"Origin": "https://foreign.example"}).status_code, 403)
        self.assertEqual(self.client.get("/api/credits", base_url="http://foreign.example").status_code, 403)
        self.assertEqual(self.client.put("/api/credits/12/aliases", data="aliases=alias").status_code, 415)
        self.assertEqual(self.client.put("/api/credits/12/aliases", json={"aliases": [], "name": "New identity"}).status_code, 400)
        self.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
