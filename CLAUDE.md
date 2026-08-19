# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A single-purpose automation: [`new_release_main.py`](new_release_main.py) reads the
Spotify artists the user follows, finds their releases from the last 3 days, and
maintains a private playlist named **"New Releases"** — adding new tracks to the
top and removing anything added more than 14 days ago. It runs on a schedule via
[`.github/workflows/daily.yml`](.github/workflows/daily.yml).

There is no test suite, no framework, and no build step. The whole program is one
`main()` with numbered comment sections (`# 2) …`, `# 7) …`); keep that structure
and numbering intact when editing.

## Running it

```bash
pip install -r requirements.txt
python new_release_main.py
```

Credentials come from `SPOTIPY_CLIENT_ID` / `SPOTIPY_CLIENT_SECRET` /
`SPOTIPY_REDIRECT_URI`, read from `.env` locally and from Actions secrets in CI.
`SPOTIFY_TOKEN_CACHE_PATH` overrides where the OAuth token cache lives (CI writes
it to a temp file from the `SPOTIFY_TOKEN_CACHE` secret).

Do not run the script to "verify" a change unless asked: every run mutates the
user's real playlist and spends Spotify API quota. Prefer `python -m py_compile`
and reading the code.

## Things that bite

- **Spotify responses have holes in them.** Playlist items can come back with a
  `null` `track` (catalog removals, market-unavailable tracks), paginated
  responses can omit `items`, and `duration_ms` can be `null`. Guard before
  subscripting — an unguarded index here is what breaks the nightly run.
- **Re-running is safe by design.** Tracks already in the playlist are filtered
  out by URI before adding, so a duplicate run is a no-op rather than a
  double-add. Preserve that property.
- **Batch every write.** Spotify caps add/remove calls at 100 URIs; use
  `remove_in_batches` and the `BATCH_SIZE` loop rather than passing a full list.
- **Per-artist failures are swallowed on purpose.** The `try/except` around each
  artist prints a warning and continues so one bad artist can't kill the run.

## The workflow

Two `schedule` entries fire at 21:07 and 21:37 UTC. They are deliberately offset:
GitHub's scheduler has been running this repo's jobs ~3h late, so firing the
evening before lands the actual execution in the intended 00:00–01:00 UTC window
(02:00–04:00 Israel time year-round). The second entry is a retry, not a second
update — a guard step queries `gh run list` and skips if a scheduled run already
succeeded today. The guard fails open (runs the script) if the lookup errors, and
never skips `workflow_dispatch`, so manual runs exercise it live.

The keepalive step exists because GitHub disables scheduled workflows after 60
days without commits; it pushes an empty commit once the last commit is 50+ days
old, and runs even when the script fails.

If you change the cron entries, update both the comment block above them and the
README's scheduling section — they restate the reasoning and go stale silently.

## Conventions

- Comments explain *why*, not what. Match that when adding them.
- Keep code PEP 8 / autopep8-clean.
- Do not commit `.env`, `token.json`, or any token cache.
