# Reviewed catalog-import commits

Branch: `review/catalog-import-approved`, in the `catalog-import-review` worktree.
These are the reviewed versions, not the original feature branch's commit hashes.
One chapter describes one capability; ordinary tests accompany each change.

| Chapter | Reviewed commit | High-level purpose |
| --- | --- | --- |
| 1 | `0d91026` | Fetch source details for the Veritas sample |
| 2 | `59cd88c` | Prepare audio and covers locally |
| 3 | `9b4c232` | Review and save the sample in a browser |
| 4 | `5f42d24` | Store import identities and release metadata |
| 5 | `4ad2dc4` | Store immutable media in the configured R2 bucket |
| 6 | `32d40e1` | Import reviewed albums and tracks through the API |
| 7 | `a22c6ef` | Publish selected tracks from the tool |
| 8 | `05f5787` | Discover Kivo candidates and remember decisions |
| 9 | `efd5e6a` | Keep separate saved reviews for each release |
| 10 | `a6be9cd` | Map source tracks and renamed labels to releases |
| UI follow-up | `07f2df5` | Keep a dark theme and tidy review layouts |
| 11 | `5d0c638` | Refresh media without losing previous valid files |
| 12 | `123d621` | Separate display order from official track numbers |
| 13 | `50bc1f2` | Review incoming source changes with Use/Keep |
| 14 | `0209452` | Count plays directly in PostgreSQL, without Redis |
| 15 | `07958f2` | Reject outdated publication revisions |
| Concurrency follow-up | `36f0ae0` | Handle simultaneous first-time album creation |
| 16 | `de6d1c3` | Compare published values and resolve conflicts before retrying |
| 17 | This guide's commit | Verify the complete retry flow with isolated PostgreSQL/MinIO |

Chapter 17 adapts original `cd7387a`; it does not restore the removed H2/local-media
runtime profile. H2 stays test-only. Everyday development uses development
PostgreSQL and a separate development R2 bucket; the optional verification stack
uses local MinIO. The setup and safety boundaries are in [README.md](README.md).

The frontend is a separate repository, with its own media-URL/category/numbering
changes. Completing these backend chapters is not a frontend review or completion
of the whole pipeline. See [remaining work and evidence](PIPELINE.md).
