# Blue Archive Music API

Spring Boot backend for the Blue Archive Music app. It provides song, album, category, media metadata, and play-count APIs for the frontend.

## Current Features

- Public song, album, and category endpoints
- Song play-count tracking with atomic database increments
- PostgreSQL schema management with Flyway
- Cloudflare R2 media storage configuration
- Railway-ready production configuration
- Temporary admin API key protection for admin endpoints

## Local Development

Use Java 17+, Docker Desktop, Node.js/npm, Python 3.11+, and FFmpeg/FFprobe.
Copy `.env.example` to the ignored `.env.local` and fill in development credentials.
The database is `blue_archive_api` on `localhost:5433`; the media bucket is
`bluearchive-music-dev`. Use R2 credentials scoped to that development bucket.

Install dependencies once from this repository root:

```powershell
python -m pip install -r tools/catalog-import/requirements.txt
npm.cmd --prefix ../blue_archive_music/client ci
```

In the frontend's ignored `.env.local`, set `VITE_API_BASE_URL=http://localhost:8080`
and `VITE_PUBLIC_MEDIA_BASE_URL` to the development R2 bucket's public URL.
Never put private credentials in `VITE_` settings.

Run these commands from this repository root, in this order. The database command
starts PostgreSQL in the background. Use a separate PowerShell terminal for each
remaining service; wait for PostgreSQL to accept connections and then for the
backend to start.

```powershell
.\scripts\dev.ps1 -Service database
.\scripts\dev.ps1 -Service backend
.\scripts\dev.ps1 -Service frontend
.\scripts\dev.ps1 -Service catalog
```

Open the app at <http://localhost:5173> and the private import tool at
<http://127.0.0.1:8765>. Backend health is <http://localhost:8080/health>.
Ctrl+C stops the backend, frontend, or import tool in its terminal. The database command reuses Compose
project `bluearchivemusicapi`, container `ba-postgres`, and its existing named
volume. The backend disables automatic Compose lifecycle management.

The launcher loads `.env.local` explicitly and keeps credentials out of its output.
Optional `-EnvFile`, `-FrontendDirectory`, and `-ReviewDirectory` parameters support
other local paths. Saved reviews and prepared media normally live in
`tools/catalog-import/data`; when using a different existing data directory, pass
its absolute path with `-ReviewDirectory`. Stop the tool and back up the whole data
directory before moving saved work between directories.

Starting services never resets or cleans up databases. A fresh development database
is an explicit, one-time operation limited to `blue_archive_api`; retain reviews
and media, and reconcile old publication receipts before publishing to it. Do not
delete shared Docker volumes. The separate automated test setup uses
`application-e2e-test.yaml` and `tools/catalog-import/compose.e2e-test.yaml`; its
PostgreSQL/MinIO services and data are independent from everyday development.

To confirm the environment, publish one reviewed album, open it in the app, and
play audio. Retry unchanged publication, then publish a correction: the correction
should appear on the same album and track identities, without duplicates.

## Future Development

- Replace temporary admin API key with full Spring Security auth
- Add OAuth, JWT login, and email verification
- Add user-generated content endpoints
- Add search support
- Improve data import and content maintenance scripts
