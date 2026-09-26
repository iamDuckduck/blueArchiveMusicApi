"""Offline checks for the operator's collection and publication guidance."""

import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

from app import create_app
from catalog import Catalog


class OfficialSongCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.catalog = Catalog(self.temp.name)

    def test_standalone_song_versions_can_be_a_collection_without_album_metadata(self):
        self.catalog.merge([
            {"id": 197, "album": "", "title": "Thanks to (EN Ver)"},
            {"id": 198, "album": "", "title": "Thanks to (KR Ver)"},
        ])
        source = next(iter(self.catalog.read()["candidates"]))
        with self.assertRaises(ValueError):
            self.catalog.decide(source, "included")
        identity = str(uuid.uuid4())
        self.catalog.create_release({"id": identity, "title": "Thanks to",
                                     "category": "Blue Archive Global songs", "official": True})
        self.catalog.map_tracks(source, identity, [197, 198])
        self.catalog.decide(identity, "included")
        saved = self.catalog.open_review(identity).view()
        self.assertEqual(saved["album"]["fields"]["title"], "Thanks to")
        self.assertEqual(saved["album"]["fields"]["category"], "Blue Archive Global songs")
        self.assertEqual(saved["album"]["fields"]["release_date"], "")
        self.assertEqual(len(saved["tracks"]), 2)
        for track in saved["tracks"]:
            self.assertIsNone(track["fields"]["disc"])
            self.assertIsNone(track["fields"]["position"])
            self.assertFalse(track["included"])
            self.assertFalse(track["publish_selected"])
        self.assertEqual(saved["publication"]["status"], "pending")

    def test_official_music_confirmation_is_still_required(self):
        with self.assertRaisesRegex(ValueError, "identified official music"):
            self.catalog.create_release({"id": str(uuid.uuid4()), "title": "Any source group",
                                         "category": "Blue Archive Global songs", "official": False})

    def test_global_category_is_an_operator_choice_not_an_automatic_scan_default(self):
        self.catalog.merge([{"id": 197, "album": "Thanks to", "title": "Thanks to (EN Ver)"}])
        identity = next(iter(self.catalog.read()["candidates"]))
        self.assertEqual(self.catalog.open_review(identity).view()["album"]["fields"]["category"], "")

    def test_pages_explain_local_boundary_and_put_review_before_publish(self):
        client = create_app(self.temp.name).test_client()
        discovery = client.get("/catalog").get_data(as_text=True)
        page = client.get("/albums/veritas-vol-2/").get_data(as_text=True)
        for text in ["Blue Archive Global songs"]:
            self.assertIn(text, discovery)
            self.assertIn(text, page)
        self.assertIn("Scanning does not download or publish music.", discovery)
        self.assertIn("Import stages", page)
        self.assertIn("What do these choices mean?", discovery)
        self.assertIn("Save changes keeps your local draft. It does not publish.", page)
        self.assertLess(page.index('id="tracks"'), page.index('id="publish-heading"'))
        self.assertIn('id="next-step"', page)
        self.assertIn('data-album-field="gamekee_notes"', page)
        self.assertIn("Article summary only", page)
        self.assertNotIn("Include only identifiable official releases", discovery)


@unittest.skipUnless(shutil.which("node"), "Node.js is needed for the browser guidance checks")
class OperatorGuidanceTests(unittest.TestCase):
    def test_actual_browser_script_derives_next_action_without_network_or_server_state(self):
        script = Path(__file__).resolve().parents[1] / "static" / "review.js"
        javascript = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, {addEventListener() {}, classList:{remove() {}, add() {}}});
  return elements.get(selector);
}
const context = vm.createContext({
  document: {body: {dataset: {}}, querySelector: element},
  window: {addEventListener() {}}, setInterval() {},
  // Do not resolve the initial refresh: these tests exercise the pure state view.
  fetch: () => new Promise(() => {})
});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const initial = {
  album: {decision:'included', fields:{title:'Thanks to', category:'Blue Archive Global songs', release_date:''}, cover:{status:'ready'}},
  tracks: [{id:'197', source_id:197, included:true, publish_selected:true,
    fields:{title:'Thanks to (EN Ver)', disc:null, position:null, kind:'unsure', composer:[]},
    source:{file:'//static.kivo.wiki/musics/thanks.mp3'},
    media:{status:'ready', source_url:'https://static.kivo.wiki/musics/thanks.mp3'}}],
  publication:{enabled:true, destination:'http://127.0.0.1:18083', destinations:{}},
  job:{running:false}
};
function result(change = () => {}, dirty = false) {
  context.testState = structuredClone(initial);
  change(context.testState);
  context.hasChanges = dirty;
  return JSON.parse(vm.runInContext('JSON.stringify(nextOperatorStep(testState, hasChanges))', context));
}
assert.equal(result().canPublish, true, 'unknown dates, credits and numbering are allowed');
assert.equal(result().stage, 'publish');
assert.equal(result(s => {s.album.decision = 'review'}).stage, 'include');
assert.equal(result(s => {s.tracks[0].included = false}).stage, 'include');
assert.equal(result(s => {s.album.cover.status = 'failed'}).stage, 'prepare');
assert.equal(result(s => {s.album.fields.category = ''}).href, '#details');
assert.equal(result(s => {s.tracks[0].publish_selected = false}).stage, 'review');
assert.equal(result(s => {s.publication.enabled = false}).canPublish, false);
assert.equal(result(() => {}, true).canPublish, false);
assert.equal(result(s => {s.tracks[0].pending_index = {title:'New source name'}}).href, '#fetch');
assert.equal(result(s => {s.tracks[0].source.file = 'https://static.kivo.wiki/new.mp3'}).stage, 'prepare');
assert.equal(result(s => {s.tracks[0].pending_suggestions = {kivo:{title:'New name'}}}).href, '#track-197');
assert.equal(result(s => {s.tracks[0].fields.title = ''}).canPublish, false);
assert.equal(result(s => {s.publication.destinations[s.publication.destination] = {conflict:'197'}}).href, '#published-panel');
assert.equal(result(s => {s.job = {running:true, action:'publish', message:'Sending selected tracks'}}).canPublish, false);
assert.equal(result(s => {s.job = {running:true, action:'published', message:'Checking'}}).stage, 'review');
const partial = result(s => {
  s.tracks.push({id:'198', source_id:198, included:true, publish_selected:false,
    fields:{title:'Other version'}, media:{status:'failed'}, pending_index:{title:'Source changed'}});
});
assert.equal(partial.canPublish, true, 'unselected unfinished tracks must not block selected music');
assert.match(partial.message, /1 other included track will not be sent/);

// The retry/link follow the edited reference, not the last fetched reference.
const oldUrl = 'https://www.gamekee.com/ba/691994.html';
const newUrl = 'https://www.gamekee.com/ba/692001.html';
context.testState = structuredClone(initial);
context.testState.album.fields.gamekee_url = newUrl;
context.testState.gamekee = {status:'ready', url:oldUrl, text:'Old article', summary:'Old summary', article:{title:'Old title'}};
vm.runInContext('renderGamekee(testState)', context);
assert.equal(element('#retry-gamekee').disabled, false, 'a newly saved URL can be checked');
assert.equal(element('#gamekee-link').href, newUrl);
assert.equal(element('#gamekee-status').textContent, 'Not checked');
assert.equal(element('#gamekee-evidence').hidden, true);
assert.equal(element('#gamekee-summary').hidden, true);
assert.equal(element('#gamekee-text').textContent, '');
assert.equal(element('#gamekee-article-title').textContent, '');
context.testState.gamekee.url = newUrl;
vm.runInContext('renderGamekee(testState)', context);
assert.equal(element('#gamekee-evidence').hidden, false, 'matching evidence is shown');
assert.equal(element('#gamekee-summary').hidden, false);
vm.runInContext("pending.album.gamekee_url = ''; renderGamekee(testState)", context);
assert.equal(element('#retry-gamekee').disabled, true, 'clearing the URL immediately disables retry');
assert.equal(element('#gamekee-link').hidden, true);
assert.equal(element('#gamekee-evidence').hidden, true);
vm.runInContext("pending.album.gamekee_url = 'https://www.gamekee.com/ba/692002.html'; renderGamekee(testState)", context);
assert.equal(element('#retry-gamekee').disabled, false, 'checking an unsaved new URL saves it first');
assert.equal(element('#gamekee-summary').hidden, true);
assert.equal(element('#gamekee-article-title').textContent, '');
console.log('Operator guidance states passed.');
"""
        result = subprocess.run([shutil.which("node"), "-e", javascript, str(script)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
