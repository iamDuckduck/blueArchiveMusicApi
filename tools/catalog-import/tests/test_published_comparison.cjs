const test = require('node:test');
const assert = require('node:assert/strict');
const {publicationRows} = require('../static/published-comparison.js');
const hash = 'a'.repeat(64);
const key = `catalog/identity/${hash}.jpg`;
function fixture() {
  return {album:{fields:{title:' Thanks to ', category:'Music', release_date:'', notes:''}, cover:{files:{'800':{sha256:hash}}}},
    tracks:[{id:'255', fields:{title:'Track', disc:null, position:null, display_order:2, kind:'vocal', notes:'',
      group:['Unit', 'Unit'], composer:['Nor'], performers:[{character:'Chihiro', voice_actor:'Voice'}]}, media:{sha256:hash}}]};
}
test('album labels map, title trims, dates remain optional, local-only fields stay hidden', () => {
  const state = fixture();
  state.album.fields.gamekee_url = 'local-only';
  const rows = publicationRows('album', state, {exists:true, metadata:{title:'Thanks to', category:'Music', releaseDate:null, description:''}, media:{cover800:key,coverImage:key}});
  assert.ok(rows.every(row => row.same));
  assert.equal(rows.find(row => row.label === 'Title').draft, 'Thanks to');
  assert.equal(rows.some(row => row.label.includes('gamekee')), false);
});
test('published display-cover differences cannot disappear behind matching cover800', () => {
  const rows = publicationRows('album', fixture(), {exists:true, metadata:{}, media:{cover800:key,coverImage:`catalog/identity/${'b'.repeat(64)}.jpg`}});
  assert.equal(rows.find(row => row.label === '800 px cover').same, true);
  assert.equal(rows.find(row => row.label === 'Displayed cover').same, false);
});
test('credits normalize names, duplicates, performers and role order', () => {
  const state = fixture();
  const rows = publicationRows('255', state, {exists:true, metadata:{credits:[{type:'COMPOSER',name:'Nor'}, {type:'ARTIST',name:'Chihiro / Voice'}, {type:'ARTIST',name:'Unit'}]}, media:{audio:key}});
  assert.equal(rows.find(row => row.label === 'Artists / performers').same, true);
  assert.equal(rows.find(row => row.label === 'Composers').same, true);
  state.tracks[0].fields.kind = 'instrumental';
  const instrumental = publicationRows('255', state, {exists:true, metadata:{credits:[{type:'ASSOCIATED',name:'Chihiro / Voice'}]}, media:{}});
  assert.equal(instrumental.find(row => row.label === 'Associated characters / voices').same, true);
});
test('unknown media keys are marked unverified, not falsely matching', () => {
  const row = publicationRows('255', fixture(), {exists:true, metadata:{}, media:{audio:'legacy/file.mp3'}}).find(row => row.label === 'Audio');
  assert.equal(row.unknown, true);
  assert.equal(row.same, false);
  assert.match(row.draft, /unavailable/);
});
test('missing published record is distinct from matching empty metadata', () => {
  const rows = publicationRows('album', fixture(), {exists:false,metadata:{},media:{}});
  assert.equal(rows[0].published, 'Not published');
  assert.equal(rows[0].same, false);
});
