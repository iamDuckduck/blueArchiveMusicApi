# Catalog import — reviewed progress

Updated: 2026-09-20. Branch: `review/catalog-import-approved`.

The owner-led backend review covers [chapters 1–17](HISTORY.md). The general
pipeline is still unfinished. Stop after this verification checkpoint; do not
resume goal-mode work or start the remaining features without the owner's request.

## What is implemented

| Operator step | Reviewed behavior |
| --- | --- |
| Scan | Read paginated Kivo records and form candidate groups; preserve earlier data when scans fail. A source grouping is not necessarily an album. |
| Choose | Remember include/skip/grouping/review decisions and deliberately map source tracks to identified releases. |
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

This run verifies backend/storage delivery, not a fresh frontend browser playback
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

## What remains — discuss before implementing

1. Reliable GameKee retrieval/matching and broader source-reader validation.
   The previously sampled GameKee request returned HTTP 567; keep the visible
   manual-reference fallback rather than claiming unattended reliability.
2. Structured character/voice-actor credits, aliases and credit-aware search.
   Existing reviewed names/roles work, but they do not complete searchable identities.
3. Representative release checks and a backed-up catalog rebuild/migration plan.
   One Veritas sample does not establish whole-catalog correctness. Do not delete
   existing records or media without a separately reviewed replacement plan.
4. Complete development-R2 CORS/public-URL and frontend playback verification.
   MinIO HTTP ranges prove media delivery, not the actual browser player or R2 setup.

After the pipeline and catalog stage: Google sign-in/private libraries, then
AWS/domain launch. Those are later stages, not part of chapter 17.

## Boundaries to preserve

- Official identified releases, including singles; broad source groups are not albums.
- Drama remains excluded; missing tracks stay visible and can remain unselected.
- Credits cover artists/groups, composers and character/CV pairs, not lyricists.
- Human approval to include, prepare or save never implies approval to publish.
- Keep prior media and unrelated working changes; no automatic destructive cleanup.
- No Redis play-count worker: each play performs a direct atomic database increment.
- Local processing first; hosted administration, queues and scheduled imports can wait.

See [setup and verification commands](README.md). Broader product decisions live
in the parent workspace's `docs/`, outside this backend Git repository.
