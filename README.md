# Blue Archive Music API

Spring Boot backend for the Blue Archive Music app. It provides song, album, category, media metadata, and play-count APIs for the frontend.

## Current Features

- Public song, album, and category endpoints
- Song play-count tracking with Redis
- PostgreSQL schema management with Flyway
- Cloudflare R2 media storage configuration
- Railway-ready production configuration
- Temporary admin API key protection for admin endpoints

## Local Development

```bash
./mvnw spring-boot:run
```

Use a local profile and environment variables for database, Redis, and R2 settings. Do not commit local secrets.

## Future Development

- Replace temporary admin API key with full Spring Security auth
- Add OAuth, JWT login, and email verification
- Add user-generated content endpoints
- Add search support
- Improve data import and content maintenance scripts
