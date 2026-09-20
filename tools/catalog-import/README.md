# Local catalog review

Requires Python 3.11+, FFmpeg and FFprobe on PATH. From this directory:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8765. Load Kivo details, include the Veritas album,
prepare its audio and artwork, review the source evidence and edit the credits.
Save changes to keep your corrections across restarts. The page previews the
validated audio and keeps the spoken drama reference excluded.

Fetching reads source metadata and file URLs. Preparation downloads and validates
those files, reads embedded tags and creates 400/800 px cover copies. GameKee
requests can fail; the saved error and manual reference remain available.

The ignored `data/` directory contains SQLite reviews and prepared media.
Stop the tool and back up that whole directory before moving your saved work.
Use `--data-dir` for a separate review directory and `--port` for another port.

Run `python -m unittest discover -s tests -v` for the source, preparation,
persistence and local browser-API tests. Fixtures and temporary files keep these
tests independent from live source services.

The browser tool discovers release candidates and keeps separate saved reviews
and media for each release, alongside the original Veritas sample. Detailed
per-field incoming-change review remains a later chapter.

## Backend development and media storage

Everyday local development and manual testing use the normal `dev` profile:
development PostgreSQL and a dedicated development R2 bucket. There is
no separate H2/local-media application profile or `/media/` route in this chapter.
Production uses the `prod` profile with its own database and R2 settings.

Load the backend's ignored environment file through your IDE/run configuration;
Spring Boot does not automatically load arbitrary `.env` files. Use these existing
variables (never commit real credentials):

```dotenv
SPRING_PROFILES_ACTIVE=dev
POSTGRES_DATASOURCE_URL=jdbc:postgresql://localhost:5432/<development-database>
POSTGRES_USER=<development-user>
POSTGRES_PASSWORD=<development-password>
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
R2_BUCKET=bluearchive-music-dev
R2_ACCESS_KEY=<development-bucket-only-access-key>
R2_SECRET_KEY=<development-bucket-only-secret>
```

Use a token scoped only to the development bucket. Profile names do not enforce
isolation: check database and bucket values before a run. Do not load production
credentials into the development process. Start with `mvn spring-boot:run` after
loading the environment. The existing dev profile starts Docker Compose; if
your development services are already managed elsewhere, set
`SPRING_DOCKER_COMPOSE_ENABLED=false`.

The storage component uses the selected R2 bucket and immutable keys of the form
`catalog/<identity-hash>/<content-hash>.<extension>`. Both images and audio use
this layout; it has no configurable environment prefix. Separate buckets provide
dev/prod separation without changing those keys. Identical retries reuse stored
objects, replacements retain prior files, and failed database transactions log
potentially unreferenced objects instead of deleting them automatically.

Tests use in-memory H2, mocked object storage and temporary files, without live
credentials. H2 is a test-only dependency; it does not verify PostgreSQL migrations
or real R2 access. Run `mvn test` from the backend root.

For an explicit real-R2 smoke check, load only the development settings above,
set `CATALOG_R2_SMOKE=true`, `CATALOG_SMOKE_AUDIO` to the reviewed Veritas 255 MP3,
and `CATALOG_SMOKE_PUBLIC_BASE` to the development bucket's public base URL. Run
`mvn -Dtest=CatalogMediaR2SmokeTest test`. This opt-in test requires a dev-labelled
bucket, stores/reuses one stable sample object, checks MIME/public byte ranges,
and reports the CORS response for `http://localhost:5173`. It retains the object,
does not start a database, and does not prove browser playback or token scope.
Unset `CATALOG_R2_SMOKE` afterward; ordinary test runs skip this network check.

Review check (2026-09-14): the development R2 upload, unchanged retry and public
MP3 byte-range checks passed with reviewed Veritas 255 audio. The stable smoke
object is retained in the development bucket. The public response did not include
`Access-Control-Allow-Origin` for `http://localhost:5173`; browser CORS behavior
and full app playback remain unverified. No database or production writes were made.

Storage was introduced in chapter 5, the import API in chapter 6, and the
review tool's Publish button in chapter 7.
The later frontend media resolver needs `VITE_PUBLIC_MEDIA_BASE_URL` pointing to
the development bucket's public URL, not the authenticated R2 upload endpoint.
Never expose R2 credentials in frontend variables. Full publish/playback and
PostgreSQL verification must be repeated when those later chapters are reviewed.

## Reviewed import API (chapter 6)

Set `ADMIN_API_KEY` in the backend environment. Calls require that value in the
`X-Admin-Api-Key` header. Publish the album before its tracks:

- `PUT /admin/catalog-import/{source}/albums/{sourceAlbumId}` accepts multipart
  parts `metadata` (JSON), `coverOriginal`, `cover400` and `cover800` (files).
- `PUT /admin/catalog-import/{source}/albums/{sourceAlbumId}/tracks/{sourceTrackId}`
  accepts multipart parts `metadata` (JSON) and `audio` (file).

Source identities select existing records independently of titles. A repeat
request updates the same record, reuses unchanged stored media and retains an
existing play count. Responses include `albumId`, `songId` (null for an album),
`created`, `status` and `revision`. Shared artists are matched by reviewed display name and
linked by role; character/CV pairs currently become combined display names.

The automated API check uses test-only H2 and temporary files.
It verifies authentication, album-before-track validation,
repeated publication, public album metadata, stable IDs/credits/play counts and
unchanged stored bytes. It does not call real R2, PostgreSQL or a browser, and it
does not reintroduce the removed local-media route. Revision checks are described
below; full publish-to-player verification remains later review work.

## Outdated publication protection (chapter 15)

Authenticated GET requests at the album and track import URLs return the current
metadata, media keys and a content fingerprint (`revision`). Changed existing
content must be published with its last reviewed revision in the
`X-Catalog-Revision` header. A stale or missing revision returns HTTP 409 with
the current state, before writing media. Play counts and audit dates do not
change the fingerprint. Identical content returns `unchanged` without writes,
so retrying after a lost success response remains safe.

For example, if one review publishes a corrected title, an older review cannot
silently overwrite that correction while publishing a composer change. It must
compare the latest content and accept a new baseline first. Existing import
records are locked during publication so competing updates are checked in order.

Chapter 15 follow-up: simultaneous first-time album creation is resolved by the
album identity unique constraint. The losing transaction rolls back, then retries
once in a fresh transaction with the original requested revision: identical
content returns `unchanged`, while different content returns 409 with the winner's
state. Only this specific unique-constraint collision is retried; other database
errors are not swallowed. Tests force both requests to observe a missing album
before either inserts it. Revision decisions now use named outcomes, and media
prediction/storage share the same key calculation.

This is not a redesign of upload transactions: locks still span media storage,
and a losing create may already have stored immutable media. Potential orphan
files are logged and retained for deliberate cleanup, not automatically deleted.

The Python comparison interface in chapter 16 sends the saved revision and helps
review conflicts before retrying. Tests cover stale drafts, identical retries,
edits outside the import endpoint and competing updates using H2 and temporary
media; real PostgreSQL/R2 verification remains separate.

## Direct play counting (revised chapter 14)

`POST /user/song/{id}/play` now performs one transactional, atomic database
increment of `play_count`; it does not load and save the whole song. Existing
songs still return 202, unknown IDs return 404, and a null counter starts at one.
There is no background polling or Redis dependency. No plays means no counter
queries. Concurrent-play tests verify increments and unchanged song metadata in
H2; they do not establish PostgreSQL concurrency or simultaneous import safety.

Before upgrading an existing Redis-based deployment, stop incoming play writes,
let the old scheduler drain pending `songPlayCounts::*` counters, and verify they
were persisted before stopping the old backend. This change does not migrate
pending Redis counts or remove any running Redis service or stored data.

## Publish selected reviewed tracks

Start the backend with its normal development settings above, including
`ADMIN_API_KEY`. Load these variables into the Python process (it does not
automatically read a `.env` file):

```dotenv
CATALOG_IMPORT_BACKEND_URL=http://127.0.0.1:8080
CATALOG_IMPORT_API_KEY=<same value as backend ADMIN_API_KEY>
```

Start `python app.py`; `--backend-url` can override the destination. Without an
API key publication is disabled. The backend, not Python, selects the database
and R2 bucket. Confirm the URL points to your development backend before publishing.

After preparation, review publication selections and click Publish reviewed album.
The tool saves edits, publishes album metadata/covers first, then selected track
metadata/audio. Missing tracks can remain visible and unselected. Each successful
response is saved locally. If a later track fails, earlier successes remain;
retrying sends the same identities again so the API can reuse records and media.
Fetching, preparation and saving edits alone do not publish anything.

These tests mock the HTTP backend. Full PostgreSQL/R2/browser verification of this
reviewed flow remains separate; this chapter does not prove live app playback.
## Discover candidates

Open `/catalog` and scan Kivo to read every index page. Include, skip or mark candidates as source groupings. Failed or inconsistent scans retain the previous complete scan. Open a release candidate's saved review to inspect and correct it separately.

For a discovery-only manual check, run these commands from this tool directory:

```powershell
Remove-Item Env:CATALOG_IMPORT_API_KEY -ErrorAction SilentlyContinue
python app.py --port 8766 --data-dir ../../target/catalog-discovery-review
```

Open `http://127.0.0.1:8766/catalog`, scan, inspect a candidate's source records,
and save an include/skip/review decision. Reload the page, then stop/restart the
tool and confirm the choice remains. This directory is separate from your saved
Veritas review. Scanning needs internet access to Kivo, but no Spring backend,
PostgreSQL or R2. With the Python API key unset, publication is disabled.

## Separate release reviews

Open a candidate’s saved review from discovery. Each release has its own SQLite review, media folder and album-scoped URL. New tracks enter unselected; missing records and corrections are retained. GameKee references are chosen per release. The original Veritas workspace remains available at `/`.

Reviews are stored in `releases/<stable-id>/reviews.sqlite3` under the chosen
data directory, with media alongside them. Opening a review does not download or
publish music. For a manual isolation check, open two candidates in separate tabs,
edit and save one title, and confirm the other review is unchanged. Reload and
restart the tool to check persistence. New tracks must be selected deliberately;
they are not automatically included for preparation or selected for publication.

## Map release appearances

Create an identified official release and map selected source tracks into it. The same recording can have separate album appearances. Link renamed source labels to existing releases without discarding saved reviews.

## Refresh source and media

Explicit refresh downloads and validates again even at an unchanged URL. Failed or interrupted replacement retains prior validated files. Identical bytes reuse paths; changed audio or artwork requires publication reselection.

## Display order

Display order controls the album sequence independently of nullable official disc/track numbers. New tracks append after the reviewed sequence. The import API requires positive `displayOrder`; migration V1.10 backfills existing order without inventing official numbers.

## Review changed source fields

Changed Kivo/tag fields appear beside reviewed values. Use a suggestion or keep the reviewed value for each field; unresolved proposals block selected-track publication. Decisions persist and clear publication selection.

## Compare published content (chapter 16)

Publication receipts and reviewed revisions are saved separately for each backend
URL. Check published state reads the latest content without uploading or advancing
your saved revision. The comparison shows changed fields first; matching fields
and technical details are optional.

If publishing meets a newer version, it pauses with the published values beside
your saved draft. Edit my draft takes you back to the local fields. Keep my values
for next publish asks for confirmation before accepting the shown revision as the
new starting point. Neither action publishes; confirmation keeps the draft/media
and clears selection (all tracks for an album, only that track for a track).
Re-select reviewed tracks and publish separately when ready.

Publication sends the album first, then selected tracks. Progress records which
items were saved, conflicted or not sent; earlier successful records are not rolled
back. Unconfirmed requests can be checked/retried using the same source identities.
Prepared files must still match their saved validation hashes before upload.

Run `node --test tests/test_published_comparison.cjs` for field comparison checks,
alongside the Python tests above. The local conflict preview was browser-checked
with fake data; these checks do not publish to PostgreSQL or R2.
