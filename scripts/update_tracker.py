#!/usr/bin/env python3
"""Collect the public Chess.com rated-puzzle rating and render a progress chart.

The official Chess.com PubAPI exposes tactics highest/lowest ratings but does not
expose the current tactics rating. This script therefore reads the exact
statsInfo.stats.rating field from the public endpoint used by Chess.com's puzzle
stats page. That endpoint is undocumented and may change; if the expected field
is missing, the script stops without recording a guessed value.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"
HISTORY_PATH = DATA_DIR / "puzzle_rating_history.csv"
LATEST_PATH = DATA_DIR / "latest_rating.json"
CHART_PATH = ASSETS_DIR / "puzzle-rating.png"

DEFAULT_USERNAME = "praj-bhatt"
PUZZLE_STATS_URL = "https://www.chess.com/callback/stats/tactics2/new/puzzles/{username}"
PROFILE_URL = "https://www.chess.com/member/{username}/stats/puzzles?time=0"
CSV_FIELDS = ["observed_at_utc", "observed_date", "rating", "username", "source"]


class RatingFetchError(RuntimeError):
    """Raised when the current puzzle rating cannot be verified."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def extract_current_rating(payload: Any) -> int:
    """Return the exact current rated-puzzle value, not best/lowest or Rush score."""
    if not isinstance(payload, dict):
        raise RatingFetchError("Chess.com returned JSON that was not an object.")

    try:
        raw_rating = payload["statsInfo"]["stats"]["rating"]
    except (KeyError, TypeError):
        raise RatingFetchError(
            "The expected statsInfo.stats.rating field was not present. "
            "Chess.com may have changed its undocumented response; no rating was recorded."
        ) from None

    # Avoid accepting booleans, empty strings, null, or other non-rating values.
    if isinstance(raw_rating, bool) or raw_rating is None:
        raise RatingFetchError("Chess.com did not return a numeric current puzzle rating.")
    if isinstance(raw_rating, int):
        rating = raw_rating
    elif isinstance(raw_rating, float) and raw_rating.is_integer():
        rating = int(raw_rating)
    elif isinstance(raw_rating, str) and raw_rating.strip().isdigit():
        rating = int(raw_rating.strip())
    else:
        raise RatingFetchError("Chess.com returned a non-integer puzzle rating.")

    # Defensive range check catches accidentally parsing an unrelated field.
    if rating < 1 or rating > 10000:
        raise RatingFetchError(f"Chess.com returned an implausible puzzle rating: {rating}.")
    return rating


def create_http_session() -> requests.Session:
    """Create a polite GET-only session with retries for transient network failures."""
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1.5,
        status_forcelist=(408, 425, 429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_current_rating(username: str) -> tuple[int, str]:
    """Fetch the live puzzle rating from Chess.com's public puzzle-stats endpoint."""
    url = PUZZLE_STATS_URL.format(username=username)
    headers = {
        "Accept": "application/json",
        "User-Agent": "chess-puzzle-rating-tracker/1.1 (public profile tracker)",
    }
    try:
        with create_http_session() as session:
            response = session.get(url, headers=headers, timeout=(10, 30))
            response.raise_for_status()
    except requests.RequestException as exc:
        raise RatingFetchError(f"Could not fetch Chess.com puzzle stats after retrying: {exc}") from exc

    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError:
        raise RatingFetchError(
            "Chess.com returned a non-JSON response (possibly a temporary block or endpoint change). "
            "No rating was recorded."
        ) from None

    return extract_current_rating(payload), url


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_PATH.exists():
        with HISTORY_PATH.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
    if not LATEST_PATH.exists():
        username = os.environ.get("CHESSCOM_USERNAME", DEFAULT_USERNAME)
        write_json_atomic(
            LATEST_PATH,
            {
                "username": username,
                "rating": None,
                "timestamp_utc": None,
                "source": None,
                "profile_url": PROFILE_URL.format(username=username),
                "status": "No successful automated sample yet",
            },
        )


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(value, tmp, indent=2, ensure_ascii=False)
        tmp.write("\n")
        temp_path = Path(tmp.name)
    temp_path.replace(path)


def read_history() -> list[dict[str, str]]:
    if not HISTORY_PATH.exists():
        return []
    with HISTORY_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            if not row.get("rating"):
                continue
            try:
                rating = int(row["rating"])
            except (TypeError, ValueError):
                continue
            if rating < 1 or rating > 10000:
                continue
            rows.append({field: (row.get(field) or "") for field in CSV_FIELDS})
        return rows


def append_history(timestamp: str, rating: int, username: str, source: str) -> None:
    # Append only after the response has passed exact-field and range validation.
    file_has_header = HISTORY_PATH.exists() and HISTORY_PATH.stat().st_size > 0
    with HISTORY_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_has_header:
            writer.writeheader()
        writer.writerow(
            {
                "observed_at_utc": timestamp,
                "observed_date": timestamp[:10],
                "rating": rating,
                "username": username,
                "source": source,
            }
        )


def _row_datetime(row: dict[str, str]) -> datetime | None:
    timestamp = row.get("observed_at_utc", "").strip()
    if timestamp:
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            pass
    observed_date = row.get("observed_date", "").strip()
    if observed_date:
        try:
            # For a user-reported date without a known time, plot it on that date
            # without pretending an exact collection time was recorded.
            return datetime.combine(date.fromisoformat(observed_date), datetime.min.time(), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def render_chart(username: str) -> None:
    """Render a compact, all-time puzzle-history panel for a GitHub README.

    Every valid observation is plotted; no rolling window or time filter is
    applied. The image intentionally contains only the section title, the most
    recently verified current rating, and the history line.
    """
    rows = read_history()
    valid_rows = []
    for row in rows:
        parsed = _row_datetime(row)
        if parsed is not None:
            valid_rows.append((parsed, int(row["rating"]), row.get("source", "")))
    valid_rows.sort(key=lambda item: item[0])

    latest: dict[str, Any] = {}
    if LATEST_PATH.exists():
        try:
            latest = json.loads(LATEST_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            latest = {}

    # Match the compact, dark Chess.com-style history card: title, current
    # rating, and a clean line. No axes, dates, legends, usernames, or footnotes.
    background = "#333333"
    line_color = "#91d58b"
    point_color = "#b8f0a8"
    rating_color = "#9be58d"
    title_color = "#f2f2f2"

    plt.rcParams.update({"font.family": "DejaVu Sans"})
    fig, ax = plt.subplots(figsize=(11.5, 2.9), dpi=140)
    fig.patch.set_facecolor(background)
    ax.set_facecolor(background)
    fig.subplots_adjust(left=0.035, right=0.985, bottom=0.10, top=0.54)

    live_rating = latest.get("rating")
    if isinstance(live_rating, int) and not isinstance(live_rating, bool):
        headline = f"{live_rating:,}"
    else:
        # Do not present an old user-reported point as today's live rating.
        headline = "—"

    fig.text(0.045, 0.91, "Puzzle history", color=title_color,
             fontsize=17, weight="semibold", va="top")
    fig.text(0.045, 0.66, headline, color=rating_color,
             fontsize=24, weight="bold", va="top")

    if valid_rows:
        dates = [item[0] for item in valid_rows]
        ratings = [item[1] for item in valid_rows]
        ax.plot(
            dates, ratings,
            color=line_color,
            linewidth=2.0,
            marker="o",
            markersize=3.1,
            markerfacecolor=point_color,
            markeredgewidth=0,
            solid_capstyle="round",
            zorder=3,
        )
        # A very subtle area fill keeps a single continuous progress shape
        # without adding extra labels or chart chrome.
        floor = min(ratings) - max(35, int((max(ratings) - min(ratings)) * 0.18))
        if len(dates) > 1:
            ax.fill_between(dates, ratings, floor, color=line_color, alpha=0.08, zorder=1)

        lower = min(ratings)
        upper = max(ratings)
        padding = max(60, int((upper - lower) * 0.20))
        ax.set_ylim(max(0, lower - padding), upper + padding)
        if len(dates) == 1:
            ax.set_xlim(dates[0] - timedelta(days=14), dates[0] + timedelta(days=14))
        else:
            span = max((dates[-1] - dates[0]).total_seconds(), 86400)
            margin = timedelta(seconds=span * 0.025)
            ax.set_xlim(dates[0] - margin, dates[-1] + margin)
    else:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

    # Keep the plot itself visually silent: only the line and its data points.
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        CHART_PATH,
        facecolor=background,
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.05,
    )
    plt.close(fig)


def run(username: str) -> None:
    ensure_data_files()
    rating, source_url = fetch_current_rating(username)
    timestamp = utc_now_iso()
    append_history(timestamp, rating, username, source_url)
    write_json_atomic(
        LATEST_PATH,
        {
            "username": username,
            "rating": rating,
            "timestamp_utc": timestamp,
            "source": source_url,
            "profile_url": PROFILE_URL.format(username=username),
            "status": "ok",
        },
    )
    render_chart(username)
    print(f"Recorded current Chess.com puzzle rating {rating} for {username} at {timestamp}.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default=os.environ.get("CHESSCOM_USERNAME", DEFAULT_USERNAME))
    parser.add_argument("--render-only", action="store_true", help="Regenerate the graph from saved history without making a network request.")
    args = parser.parse_args()

    username = args.username.strip()
    if not username or "/" in username or ".." in username:
        print("ERROR: invalid Chess.com username.", file=sys.stderr)
        return 2

    ensure_data_files()
    if args.render_only:
        render_chart(username)
        print(f"Rendered {CHART_PATH} from existing history; no new rating was fetched.")
        return 0

    try:
        run(username)
        return 0
    except RatingFetchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("The previous CSV/JSON/chart remain the source of truth; no rating was fabricated.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
