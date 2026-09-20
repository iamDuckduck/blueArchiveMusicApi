# Credit profiles and search

## Quick overview

Publish the reviewed track credits first. Then use **Credit aliases** to add alternate spellings or language names to those existing profiles.

```text
Reviewed track credits → Publish → Backend credit profile
                                      ↓ add an alias
                              Music search finds its tracks
```

This follow-up lives on the separate credits/search branch. It does not replace the manual-review pipeline checkpoint or resolve the blocked GameKee content reader.

## What each name means

| Field | Purpose |
| --- | --- |
| Canonical name | The existing profile's stored display name, such as a group, composer, or `character / voice actor`. Its numeric ID remains unchanged. |
| Character / voice actor (CV) | Separate, optional fields retained from reviewed performer credits. A voice actor is not automatically a composer. |
| Alias | Another way to search for that same profile, such as a romanized name. It does not create or merge identities. |

Edit actual group, composer, or performer credits in the import review, then publish them. The alias page only edits aliases; it cannot rename profiles or change which songs credit them.

### Add aliases after publication

1. Open `/credits` in the local tool and check the displayed backend destination.
2. Search by the profile's **canonical name**. A blank search lists up to 50 profiles.
3. Select the correct profile; check its ID and any character / CV fields.
4. Enter aliases, one per line, then explicitly click **Save aliases to backend**.

Typing does not save. Save replaces that profile's alias list in the **shared backend database**, not the local album draft. An empty list removes its aliases, not the profile. Limits: 20 aliases, 255 characters each. Existing aliases survive an identical catalog reimport.

### What music search returns

The listening app can search track titles, album titles, credited groups, composers, characters, voice actors, and their aliases.

An alias finds songs directly linked to that profile. This includes an instrumental with an `ASSOCIATED` character credit—it does not claim that the character sings on the instrumental. An unrelated BGM track is **not** included merely because it shares the album. Matching the same song through multiple credit roles does not duplicate it.

## Schema and isolated verification

Migration **V1.11** adds nullable character / CV columns and a separate alias table. Existing profile IDs, display names, and song links remain intact. It does not guess how to split old combined names; reviewed imports can supply the structured fields.

The verifier starts with a fresh generated database and applies V1.1–V1.11. From this credits worktree's root, after building with `mvn package` and starting the existing verification PostgreSQL/MinIO services described in the README, run:

```powershell
python tools/catalog-import/verify_credits.py --review ../catalog-import-review/target/dev-r2-check-20260920/sample/review
```

Do not run `mvn clean`: `target` contains retained reviews and evidence. Port 18084 must be free; the verifier refuses to reuse an unknown running backend.

| Verification destination | Separation |
| --- | --- |
| Database `catalog_credits_verify_<id>` | New local test database per run; retained for inspection. |
| Backend `127.0.0.1:18084` | Verifier-owned process, stopped when the run ends. |
| MinIO `127.0.0.1:19000`, bucket `catalog-import-verify` | Local test media, not development R2. |

The source review is copied and hash-checked. Normal development databases and the development R2 bucket are not touched. Verification checks structured credits, alias search, unrelated-track exclusion, safe reimport, unchanged media, and rejected unauthenticated edits.

Latest passed report: `target/credits-live-20260920-202738-5e2ca8/report.json`.

### Current browser example

- [Credit alias demo](http://127.0.0.1:8772/credits): search `千寻`, then select `千寻 / 山村響`.
- [Listening app demo](http://127.0.0.1:15174/): search **Chihiro demo**.

`Chihiro demo` is a **test-only alias** in the isolated demo database. It finds the credited vocal and associated instrumental, not the unrelated BGM. These temporary local demo services must be running for the links to work; they are separate from normal development playback.
