const {test} = require('node:test');
const assert = require('node:assert/strict');
const home = require('../static/catalog-home.js');
const candidate = (id, source_album, extra = {}) => ({id, source_album, kind:'release_candidate', decision:'review', ...extra});
const review = (id, title) => ({id, title, decision:'included', url:`/albums/${id}/`});

test('a corrected draft joins by ID, never by its title', () => {
  const rows = home.rows({candidates:[candidate('a','Source title'), candidate('b','Corrected title')], reviews:[review('a','Corrected title')]});
  assert.equal(rows.length, 2);
  assert.equal(rows[0].title, 'Corrected title');
  assert.equal(rows[0].review.url, '/albums/a/');
  assert.equal(rows[1].review, undefined);
});

test('saved-only reviews survive an empty scan list', () => {
  const rows = home.rows({candidates:[], reviews:[review('sample','Veritas'),review('manual','Thanks to')]});
  assert.equal(rows.length, 2);
  assert.ok(rows.every(row => !home.isGroup(row)));
  assert.ok(rows.every(row => home.matches(row, 'saved', '')));
});

test('filters distinguish new, saved and skipped without implying publication', () => {
  const rows = home.rows({candidates:[candidate('a','New'),candidate('b','Draft'),candidate('c','Skip',{decision:'skipped'})], reviews:[review('b','Saved title')]});
  for (const [view, ids] of [['all',['a','b','c']],['new',['a']],['saved',['b']],['skipped',['c']]]) {
    assert.deepEqual(rows.filter(row => home.matches(row,view,'')).map(row => row.candidate.id), ids);
  }
  assert.ok(home.matches(rows[1], 'saved', 'DRAFT'));
  assert.ok(home.matches(rows[1], 'saved', 'saved title'));
});

test('source groups and linked labels remain inspectable, not duplicate albums', () => {
  const rows = home.rows({candidates:[candidate('a','Release'),candidate('b','Renamed',{redirect_to:'a'}),candidate('c','Broad',{kind:'source_grouping'}),candidate('d','Unknown',{kind:'unresolved'}),candidate('e','Reclassified',{decision:'grouping'})], reviews:[review('a','Release')]});
  assert.deepEqual(rows.filter(row => !home.isGroup(row)).map(row => row.candidate.id), ['a']);
  assert.equal(rows.filter(home.isGroup).length, 4);
});
