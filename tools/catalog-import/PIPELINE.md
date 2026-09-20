# Catalog import — reviewed progress

Updated: 2026-09-20. Branch: `review/catalog-import-approved`.

The owner-led backend review covers [chapters 1–17](HISTORY.md). The general
pipeline is still unfinished. Stop after this verification checkpoint; do not
resume goal-mode work or start the remaining features without the owner's request.

## What is implemented

| Operator step | Reviewed behavior |
| --- | --- |
| Scan | Read paginated Kivo records and form candidate groups; preserve earlier data when scans fail. A source grouping is not necessarily an album. |
| Choose | Remember include/skip/grouping/review decisions and deliberately map source tracks to identified releases or named collections of official songs. |
| Prepare | Fetch details, download/validate audio, read tags, retain original covers and make 400/800 px variants. Failed refreshes preserve valid files. |
| Review | Save corrections per release, keep official numbering optional, and require Use/Keep decisions for changed source fields. |
| Publish | Send album first, then selected tracks; reuse stable source identities and immutable media, and preserve play counts. |
| Resolve conflicts | Compare published values against the saved draft. Confirming a revision does not publish; partial successes remain saved. |

Everyday development/manual app testing uses development PostgreSQL and the
development R2 bucket. Production has separate database/bucket credentials. The
automated integration verifier uses its own local PostgreSQL and MinIO, not R2.

## Verification on the reviewed branch

Chapter 17 passed on 2026-09-20 with the reviewed backend and adapted verifier.

- Backend build: 19 tests passed, plus 1 explicitly skipped real-R2 smoke check.
- Python: 78 tests passed, including 14 verifier isolation/copy/lifecycle checks.
- JavaScript comparison: 5 tests passed.
- Final live evidence: `target/catalog-live-20260920-182132/report.json` and
  `backend.log` (ignored local artifacts). Earlier successful run:
  `target/catalog-live-20260920-181912/`.
- Final run kept album ID **7** and song IDs **12/13** through lost-response,
  partial-publication, restart and repeated-publication retries. Play count **1**
  survived; unchanged media keys/timestamps stayed unchanged.
- Ordered metadata/credits, unknown official numbers, HTTP 206 MP3 byte ranges
  and JPEG covers passed. Stale edits were rejected; explicit reconciliation
  restored the draft. Concurrent updates returned **200 and 409**.
- Flyway validated the existing V1.1–V1.10 history; this was not a fresh database
  migration replay. Existing test data was retained.
- SHA-256 checks confirmed the original SQLite review and all five prepared
  media files were unchanged after both runs. No source fetching, production
  writes or R2 calls were performed. The owned API and test containers were
  stopped; copied reviews, reports and test volumes were retained.

Isolation fixes pin effective database/media settings, exclude inherited cloud
and Java options, bypass loopback HTTP proxies, and target only the local Docker
engine. Source media paths are normalized before copying into the separate review.
These are verification-tool changes, not a new production environment.

The chapter 17 run verifies backend/storage delivery, not a fresh frontend browser playback
or real-R2/CORS check. Those limits remain explicit below.

The verifier copies the prepared Veritas review and media, uses a new test release
identity per run, and retains older runs. Its retries must reuse the same IDs and
object keys within that run. It validates the existing Flyway chain and applies
missing migrations; retained test databases are not reset to force a fresh migration.

The original branch had PostgreSQL/MinIO and browser checks on 2026-09-13. Those
are historical evidence, not a fresh browser run on this reviewed branch. The
reviewed development-R2 smoke check on 2026-09-14 passed upload/reuse/public audio
ranges, but did not establish browser playback; its response lacked CORS
allow-origin for `http://localhost:5173`. No production import is authorized by
these checks.

## Development R2 + frontend checkpoint — 2026-09-20

The owner approved one bounded Veritas check after chapter 17. No new pipeline
features were implemented; stop after this checkpoint.

- Published the approved copied review to a new local PostgreSQL database,
  `catalog_import_devcheck_20260920`, and the existing `bluearchive-music-dev`
  R2 bucket. Fresh Flyway V1.1–V1.10 migration replay passed.
- The existing `blue_archive_api` development database was backed up before
  startup and upgraded from V1.8 to V1.10. Its 45 albums / 295 songs included
  legacy Veritas records without import identities, so publication was redirected
  to the separate empty database. Do not import over the legacy catalog until
  identity backfill/rebuild is deliberately reviewed. No production was used.
- Browser checks passed: 800 px album cover, 400 px player cover, vocal then
  instrumental order, both tracks playing and advancing after seeking to ~2:31.
  The actual audio URLs used the development R2 public domain.
- A second publish returned `unchanged` for all three records. Album ID **1**,
  song IDs **1/2**, source identities **255/256**, metadata revisions, media keys
  and play counts **1/1** were preserved. Database totals stayed **1 album / 2 songs**.
- All five complete public media objects matched the prepared SHA-256 hashes.
  Their public ETag/Last-Modified values stayed the same across retry; these are
  public delivery observations, not an independent origin-side bucket audit.
- API CORS allowed `http://localhost:5173`. R2 responses still lacked an
  allow-origin header. Native audio playback succeeded without `crossOrigin`,
  so this does **not** establish fetch/Web Audio CORS support.
- Both original SQLite files and all five original media files were unchanged.
  Evidence, database backup and copied review are retained under ignored
  `target/dev-r2-check-20260920/` (see `REPORT.md`). No tracked application code
  or saved environment files changed.

At handoff the app (`http://localhost:5173/library/albums/1`), copied review tool
(`http://127.0.0.1:8770/`) and API (`http://127.0.0.1:18083`) remain running for
manual inspection. Audio is paused. They use process-only environment overrides;
ordinary launches do not automatically select this temporary database.

## Fresh candidate check — initial pause, now resolved below

On 2026-09-20 the owner deferred R2 CORS work until it causes a concrete blocker
and requested continued testing. No bucket policy was changed.

- Fresh Kivo scan in the copied workspace on port 8770 succeeded: 995 records,
  112 candidate groups. Existing source reviews were not used as prepared input.
- `Thanks to` tracks 197 (EN) and 198 (KR) downloaded and passed FFprobe/full
  FFmpeg decode validation. Both are 3:57 MP3s; the original cover and 400/800
  derivatives are ready locally. Media tags contain no usable credit metadata.
- Stopped before publication: Kivo describes an official YouTube-only song with
  no album/streaming release. The [Nexon announcement](https://www.nexongames.co.kr/bbs/board.php?bo_table=media_event_en&wr_id=190)
  confirms an official anniversary song, but does not establish a two-track album
  or digital-single release. Bounded research did not resolve that identity;
  absence of a found listing is not proof that no release exists.
- Candidate returned to `review`; prepared files retained, both publication
  selections off. No category, release date, official numbering or credits were
  invented. GameKee has no matched reference for this candidate, not a new
  confirmed HTTP 567 failure.
- The decision needed at that checkpoint was whether to keep this candidate pending under the then-current
  identified-release rule, or explicitly include official video-only songs and
  decide how to represent them. Do not silently expand catalog scope.
- Saved draft: `http://127.0.0.1:8770/albums/d7f743d6-1cf3-48fa-886a-a1da0df10a68/`.
  Local evidence: `target/fresh-release-20260920/REPORT.md`. No new publication,
  PostgreSQL/R2 writes, application-code changes or commit in this check.

## Owner decision — rebuild through the new pipeline

On 2026-09-20 the owner chose a fresh catalog rebuild through the new pipeline
instead of matching old database rows to Kivo IDs. Keep the old database and its
backup untouched; this direction is not permission to delete data or switch production.
The separate development-check database currently contains only the published
Veritas sample, not a completed replacement catalog.

Official songs do not need a formal album release to qualify. `Thanks to` is
included in the local review under `Official songs`, with EN/KR versions grouped
for browsing. The existing album container can hold this collection without
claiming an official two-track album. Its notes explain that distinction; release
date and official disc/track numbers remain blank. No schema change is needed.
Both prepared tracks remain unselected for publication; nothing new was published.

Next bounded step: review the saved `Thanks to` draft and, with publication
approval, verify it in the development catalog. Broad source groups still do not
automatically become albums. Some tool labels still say “album” or “official
release”; do not interpret those labels as a formal-album eligibility restriction.

## What remains — discuss before implementing

1. Reliable GameKee retrieval/matching and broader source-reader validation.
   The previously sampled GameKee request returned HTTP 567; keep the visible
   manual-reference fallback rather than claiming unattended reliability.
2. Structured character/voice-actor credits, aliases and credit-aware search.
   Existing reviewed names/roles work, but they do not complete searchable identities.
3. Representative checks and a fresh catalog rebuild using the new pipeline,
   not legacy source-ID backfill. One Veritas sample does not establish
   whole-catalog correctness. Review a replacement/cutover plan separately before
   deleting existing records/media or replacing the active production catalog.
4. Development-R2 CORS is deferred by the owner until a concrete need/blocker.
   Public URLs, native frontend playback and seeking pass for Veritas; they do
   not prove fetch/Web Audio CORS support. Revisit when that access is needed.

After the pipeline and catalog stage: Google sign-in/private libraries, then
AWS/domain launch. Those are later stages, not part of chapter 17.

## Boundaries to preserve

- Official releases and official standalone songs are eligible. Named browsing
  collections need not claim a formal album; broad source groups are not automatically albums.
- Drama remains excluded; missing tracks stay visible and can remain unselected.
- Credits cover artists/groups, composers and character/CV pairs, not lyricists.
- Human approval to include, prepare or save never implies approval to publish.
- Keep prior media and unrelated working changes; no automatic destructive cleanup.
- No Redis play-count worker: each play performs a direct atomic database increment.
- Local processing first; hosted administration, queues and scheduled imports can wait.

See [setup and verification commands](README.md). Broader product decisions live
in the parent workspace's `docs/`, outside this backend Git repository.
