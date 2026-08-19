# =========================================
# Spotify Weekly New Release Auto-Updater
# =========================================
import os
# Standard library imports for date/time and environment handling
from datetime import datetime, timedelta, timezone
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

MIN_DURATION_MS = 60_000


def remove_in_batches(sp, playlist_id, uris, batch_size=100):
    for i in range(0, len(uris), batch_size):
        sp.playlist_remove_all_occurrences_of_items(
            playlist_id, uris[i: i + batch_size])

# Main entry point for the script


def main():
    # Load .env, if present (no-op on platforms like GitHub Actions that
    # inject env vars directly)
    load_dotenv()

    # Spotipy reads SPOTIPY_* variables automatically:
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            scope=(
                "playlist-modify-private playlist-modify-public "
                "playlist-read-private user-follow-read"
            ),
            open_browser=False,
            cache_path=os.environ.get(
                "SPOTIFY_TOKEN_CACHE_PATH",
                os.path.expanduser("~/.cache/spotify_release_token.json"),
            ),
        )
    )
    me = sp.current_user()
    user_id = me["id"]

    # 2) Gather the list of artist IDs that the user follows
    artists = []
    after = None
    while True:
        resp = sp.current_user_followed_artists(limit=50, after=after)
        artists.extend(resp["artists"]["items"])
        if resp["artists"]["cursors"]["after"] is None:
            break
        after = resp["artists"]["cursors"]["after"]

    artist_ids = [a["id"] for a in artists]
    print(f"Found {len(artist_ids)} followed artists.")

    # 3) Identify new tracks released in the past 3 days by followed artists
    # * Use timezone-aware current time for UTC
    release_cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    # * List of keywords to exclude from new releases
    exclude_keywords = ["remix", "instrumental", "mix", "live", "version"]
    # 3.1) Collect new tracks with their release dates
    new_tracks = []  # list of dicts: {"uri": ..., "date": datetime}

    # Cap how many pages of albums/singles we'll pull per artist so one
    # prolific catalog can't blow up the run's API-call budget, while still
    # covering artists whose recent release isn't sorted into the first page.
    MAX_ALBUM_PAGES = 4  # up to 200 albums/singles per artist

    for artist_id in artist_ids:
        try:
            results = sp.artist_albums(
                artist_id, album_type="album,single", limit=50)
            albums_items = list(results["items"])
            pages = 1
            while results.get("next") and pages < MAX_ALBUM_PAGES:
                results = sp.next(results)
                albums_items.extend(results["items"])
                pages += 1

            for alb in albums_items:
                rd = alb.get("release_date")
                precision = alb.get("release_date_precision")
                if precision == "day":
                    rd_dt = datetime.strptime(
                        rd, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                elif precision == "month":
                    rd_dt = datetime.strptime(
                        rd, "%Y-%m").replace(tzinfo=timezone.utc)
                else:
                    rd_dt = datetime.strptime(
                        rd, "%Y").replace(tzinfo=timezone.utc)
                if rd_dt >= release_cutoff:
                    tracks = sp.album_tracks(alb["id"])["items"]
                    for t in tracks:
                        # ── NEW: ignore tracks shorter than one minute ──────────────────────
                        if t["duration_ms"] is not None and t["duration_ms"] < MIN_DURATION_MS:
                            continue

                        track_name = t["name"]
                        # Skip tracks containing any of the exclude keywords
                        if any(keyword in track_name.lower() for keyword in exclude_keywords):
                            continue

                        new_tracks.append({
                            "uri":  t["uri"],
                            "date": rd_dt
                        })
        except Exception as e:
            print(f"Warning: skipping artist {artist_id} due to error: {e}")
            continue

    # 4) Remove duplicate URIs, keeping only the most recent release per track
    track_map = {}
    for track in new_tracks:
        uri = track["uri"]
        date = track["date"]
        # keep the most recent date per track
        if uri not in track_map or date > track_map[uri]:
            track_map[uri] = date

    # 5) Sort the unique tracks by release date (newest first)
    sorted_tracks = sorted(
        [{"uri": uri, "date": date} for uri, date in track_map.items()],
        key=lambda x: x["date"],
        reverse=True
    )
    print(f"Found {len(sorted_tracks)} new tracks in the last 3 days.")

    if not sorted_tracks:
        print("No new releases to add.")
        return

    # 6) Automatically select (or create) the "New Releases" playlist
    playlist_name_target = "New Releases"
    playlists = []
    results = sp.current_user_playlists(limit=50)
    playlists.extend(results["items"])
    while results.get("next"):
        results = sp.next(results)
        playlists.extend(results["items"])
    # Try to find existing playlist by name (case-insensitive)
    playlist = next(
        (p for p in playlists if p["name"].strip(
        ).lower() == playlist_name_target.lower()),
        None
    )
    if not playlist:
        playlist = sp.user_playlist_create(
            user_id, playlist_name_target, public=False)
        print(f'Created new playlist: {playlist_name_target}')
    else:
        print(f'Updating playlist: {playlist_name_target}')
    playlist_id = playlist["id"]

# 7) Retrieve current tracks and timestamps from the selected playlist
    existing_items = []
    results = sp.playlist_items(
        playlist_id,
        fields="items(added_at,track(uri)),next",
        additional_types=["track"]
    )
    existing_items.extend(results.get("items") or [])
    while results.get("next"):
        results = sp.next(results)
        existing_items.extend(results.get("items") or [])

    # Spotify can return entries with a null track (removed/unavailable items)
    existing_items = [
        item for item in existing_items
        if item and item.get("track") and item["track"].get("uri") and item.get("added_at")
    ]

    # 8) Remove tracks that were added more than 14 days ago
    two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
    old_uris = [
        item["track"]["uri"]
        for item in existing_items
        if datetime.fromisoformat(item["added_at"].replace("Z", "+00:00")) < two_weeks_ago
    ]
    existing_uris = {item["track"]["uri"] for item in existing_items}

    if old_uris:
        print(f"Removing {len(old_uris)} old tracks in batches…")
        try:
            remove_in_batches(sp, playlist_id, old_uris)
        except spotipy.exceptions.SpotifyException as e:
            print("Error removing old tracks:", e)
            return
        print(f"Removed {len(old_uris)} tracks older than 14 days.")

    # 9) Filter out tracks already present in the playlist
    uris_to_add = [
        track["uri"]
        for track in sorted_tracks
        if track["uri"] not in existing_uris
    ]

    # 10) Add new tracks to the top of the playlist so newest appear first
    if uris_to_add:
        BATCH_SIZE = 100
        for idx in range(0, len(uris_to_add), BATCH_SIZE):
            batch = uris_to_add[idx: idx + BATCH_SIZE]
            # first batch goes to position 0 so newest are at top
            if idx == 0:
                sp.playlist_add_items(
                    playlist_id=playlist_id,
                    items=batch,
                    position=0
                )
            else:
                sp.playlist_add_items(
                    playlist_id=playlist_id,
                    items=batch
                )
            print(f"Added {len(batch)} tracks (batch {idx//BATCH_SIZE + 1}) "
                  f"to playlist: {playlist['external_urls']['spotify']}")
    else:
        print("Nothing new to add – playlist already up-to-date.")


if __name__ == "__main__":
    main()
