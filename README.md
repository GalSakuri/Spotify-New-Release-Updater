# Spotify Weekly New Release Auto-Updater

Automatically keeps a Spotify playlist up to date with the latest releases from the artists you follow.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Register Your Spotify App](#register-your-spotify-app)
3. [Clone & Install](#clone--install)
4. [Configure Environment Variables](#configure-environment-variables)
5. [Usage](#usage)
6. [Scheduling with GitHub Actions](#scheduling-with-github-actions)
7. [Troubleshooting](#troubleshooting)
8. [Contributing](#contributing)
9. [License](#license)

---

## Prerequisites

- **Python 3.8+**
- **pip** (Python package installer)
- A **Spotify Developer** account

---

## Register Your Spotify App

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2. Click **"Create an App"**, give it a name/description.
3. In your new app's settings, add a **Redirect URI**. It doesn't need to be a real, reachable page — it's only used once to complete the login and read the `code` param back out of the address bar (e.g. `http://127.0.0.1:5173/callback`).
4. Copy your **Client ID** and **Client Secret** for the next step.

---

## Clone & Install

```bash
# Clone this repository
git clone https://github.com/galsakuri/Spotify-New-Release-Updater.git
cd Spotify-New-Release-Updater

# (Optional) Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux
.\.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Configure Environment Variables

Spotipy reads these automatically, either from your shell environment or a `.env` file in the project root:

| Variable                | Description                                                        |
| ------------------------ | -------------------------------------------------------------------- |
| `SPOTIPY_CLIENT_ID`      | Client ID from your Spotify app                                    |
| `SPOTIPY_CLIENT_SECRET`  | Client Secret from your Spotify app                                |
| `SPOTIPY_REDIRECT_URI`   | The Redirect URI you registered above                              |
| `SPOTIFY_TOKEN_CACHE_PATH` (optional) | Where to store the cached OAuth token. Defaults to `~/.cache/spotify_release_token.json` |

Example `.env`:

```
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret
SPOTIPY_REDIRECT_URI=http://127.0.0.1:5173/callback
```

---

## Usage

```bash
python new_release_main.py
```

On the very first run, no cached token exists yet, so the script prints a Spotify authorization URL. Open it, log in, approve access, then paste the URL you're redirected to back into the terminal when prompted. This creates the token cache file, and every run after that refreshes silently with no further interaction — until Spotify invalidates the refresh token (see [Troubleshooting](#troubleshooting)).

The script will:

1. List every artist you follow.
2. Find tracks released by those artists in the last 3 days (skipping remixes, live versions, and anything under 1 minute long).
3. Create or reuse a playlist named **"New Releases"**.
4. Remove tracks older than 14 days from that playlist.
5. Add the new tracks to the top.

---

## Scheduling with GitHub Actions

The repo includes [`.github/workflows/daily.yml`](.github/workflows/daily.yml), which runs the script once a day and can also be triggered manually from the **Actions** tab ("Run workflow").

The schedule has two cron entries, at 21:07 and 21:37 UTC. That looks early, but GitHub's scheduler is best-effort and has been starting this repo's jobs roughly 3 hours late, so firing the evening before lands the actual run inside the intended 00:00–01:00 UTC window (02:00–04:00 Israel time, in both winter and summer). The second entry is a **retry, not a second update**: a guard step at the top of the job checks whether a scheduled run already succeeded today and skips if so. Manual runs never skip.

To set it up on your own fork:

1. Run the script once locally (see [Usage](#usage)) to generate a token cache file.
2. In your repo's **Settings → Secrets and variables → Actions**, add:
   - `SPOTIPY_CLIENT_ID`
   - `SPOTIPY_CLIENT_SECRET`
   - `SPOTIPY_REDIRECT_URI`
   - `SPOTIFY_TOKEN_CACHE` — the full contents of the token cache file generated in step 1
3. Push to `main`. The workflow starts running on its schedule from then on.

Re-running is harmless in any case — tracks already in the playlist are filtered out by URI before anything is added, so a duplicate run won't double-add.

Note: GitHub automatically disables scheduled workflows after 60 days with no repository activity (pushes/commits — the scheduled runs themselves don't count). If that happens, go to **Actions → Daily New Releases** and click **"Enable workflow"**.

---

## Troubleshooting

**`Warning: N playlist entries have no URI and cannot be removed automatically`**

An entry in the playlist came back from Spotify with no track attached — usually because the track was pulled from the catalog after it was added. Spotify's API identifies tracks for removal by URI, and that's exactly what these entries no longer have, so the script can't delete them. It skips them and carries on. If they build up, remove them by hand in the Spotify app.

---

**`SpotifyOauthError: invalid_grant, error_description: Refresh token expired/revoked`**

The cached refresh token was invalidated on Spotify's side — usually because access was revoked under `open.spotify.com` → your account → **Apps**, or the app's Client Secret was regenerated in the developer dashboard. There's no code fix: delete the stale token cache (locally, or the `SPOTIFY_TOKEN_CACHE` secret in Actions) and redo the login flow described in [Usage](#usage) to mint a new one.

---

## Contributing

This is a personal automation project, but issues and pull requests are welcome if you spot a bug or want to suggest an improvement.

---

## License

No license file is included. Feel free to fork and adapt for personal use.
