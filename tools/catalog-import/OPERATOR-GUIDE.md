# Import one release or official-song collection

The tool is your **local workbench**. The music app is the **published catalog**.
Nothing appears in the music app merely because you scanned, included, prepared
or saved it here.

Use **Album discovery** to find new candidates and **Saved reviews** to resume an
existing draft. The original Veritas sample appears in the same saved-review list;
opening that list does not prepare or publish music.

## The short path

1. **Scan Kivo** on `/catalog`. This reads the source music list, not audio files.
2. **Open a candidate** and decide whether it belongs in the catalog.
3. **Include the collection and tracks**, then **Prepare**. Audio and cover copies
   are downloaded and validated on this computer.
4. **Review and save** the title, category, music types, order and available credits.
   Listen to the local previews. Resolve any changed-source suggestions.
5. **Select reviewed tracks for publishing**. Confirm the displayed backend is
   your development backend, then **Publish**.
6. **Open the music app**. Check the cover, order and playback. Repeating the same
   publication should keep the same records and media, not create duplicates.

## What the choices mean

| Choice | What it means | Publishes anything? |
| --- | --- | --- |
| Needs review | Undecided; keep it for later | No |
| Include | Eligible for local preparation and review | No |
| Skip for now | Do not work on this candidate now; keep the saved data | No |
| Source grouping | A source label containing related tracks, not an approved collection | No |
| Publish selection | This prepared track has been reviewed for the next publish | Not until Publish is clicked |

For a broad source grouping, create a deliberately named collection and map only
the relevant tracks into it. Mapping is not audio downloading or publication.
Linking a renamed source label to an existing collection also does not merge two
already-reviewed albums or discard their edits.

## Example: Thanks to

- Category: **Blue Archive Global songs** (an owner-chosen browsing category).
- Collection title: **Thanks to**.
- Tracks: English and Korean versions, with display order 1 and 2.
- No formal album is required: this is a browsing collection of official songs.
- Unknown release date, disc and official track numbers stay blank.
- “Album” in the current API means the container holding those tracks; it does
  not prove that the publisher sold a formal album.

Display order tells the app which track appears first. Official disc/track numbers
describe a known release. They are different things.

## Where information comes from

| Action | Reads / creates | What stays yours |
| --- | --- | --- |
| Scan | Kivo index and candidate groups | Decisions, identities and saved reviews |
| Reload Kivo details | Current metadata and file URLs | Corrections; changed fields become proposals |
| Prepare | Missing audio, tags, original artwork and 400/800 px copies | Valid cached files and manual edits |
| Refresh source and media | Re-downloads even when URLs are unchanged | Previous valid files if replacement fails |
| GameKee Check again | Only the explicitly selected reference article | Manual notes and cached evidence for that same URL |
| Save changes | Local SQLite draft | No backend or R2 upload |
| Publish | Album metadata/covers, then selected tracks | Stable import identities and earlier successful results |

GameKee matching is deliberate: choose the article that actually describes this
collection. No match is fine. A blocked article is not an empty success; partial
article summaries are labelled as incomplete. Save manually checked reference
notes and edit the relevant review fields yourself. Notes/evidence never silently
become credits. The current GameKee CDN may return HTTP 567; the tool does not
bypass that restriction.

Manual GameKee checking in your browser is the accepted workflow when automated
retrieval is unavailable; unattended retrieval is not needed to finish this tool.

## When something changes or fails

- **Source index changed:** reload details, compare the new evidence, then review
  and select the track again. Existing corrections are not overwritten.
- **Incoming suggestion:** Use the suggestion or Keep your reviewed value.
- **Missing audio:** leave that track unselected; available approved music can publish.
- **Source audio URL changed:** prepare again and listen before selecting it.
- **Published version changed:** compare the app's values with your draft. Accepting
  a baseline does not publish; review, reselect and publish separately.
- **Interrupted publish:** an unconfirmed request may already have succeeded.
  Check published state or retry the same draft. Do not create a new identity.
- **Partial publish:** album/earlier tracks remain saved; retry finishes the rest.

## Keep development separate

Everyday development uses development PostgreSQL and the development R2 bucket.
Automated failure/retry checks use separate local PostgreSQL and MinIO. Production
has separate database/bucket credentials. The displayed URL identifies the API;
its configured environment determines the actual database and bucket.

Back up the entire review directory, including SQLite and `media/`, before moving
it. The new catalog will be rebuilt through this pipeline; the legacy database is
not automatically merged, replaced or deleted. Production cutover is a separate decision.

For commands and environment variables, see [setup](README.md). For evidence and
remaining product work, see [progress](PIPELINE.md).

After publication, this branch's [credit alias guide](CREDITS-GUIDE.md) explains
how alternate names improve search without changing the local import draft.
