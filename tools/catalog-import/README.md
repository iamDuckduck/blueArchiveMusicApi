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

This chapter demonstrates one local sample review. Later chapters add backend
publication, general discovery and review of incoming changes.

## Backend development and media storage

Everyday local development and manual testing use the normal `dev` profile:
development PostgreSQL, Redis, and a dedicated development R2 bucket. There is
no separate H2/local-media application profile or `/media/` route in this chapter.
Production uses the `prod` profile with its own database, Redis and R2 settings.

Load the backend's ignored environment file through your IDE/run configuration;
Spring Boot does not automatically load arbitrary `.env` files. Use these existing
variables (never commit real credentials):

```dotenv
SPRING_PROFILES_ACTIVE=dev
POSTGRES_DATASOURCE_URL=jdbc:postgresql://localhost:5432/<development-database>
POSTGRES_USER=<development-user>
POSTGRES_PASSWORD=<development-password>
REDIS_URL=redis://localhost:6379
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

This chapter adds storage, not the import API or Publish button (chapters 6–7).
The later frontend media resolver needs `VITE_PUBLIC_MEDIA_BASE_URL` pointing to
the development bucket's public URL, not the authenticated R2 upload endpoint.
Never expose R2 credentials in frontend variables. Full publish/playback and
PostgreSQL verification must be repeated when those later chapters are reviewed.
