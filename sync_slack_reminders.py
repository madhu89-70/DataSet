from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


EVENTS_FILE = Path(__file__).with_name("reminders.json")


def ts_to_iso_local(ts: int) -> str:
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).astimezone().isoformat()


def main() -> None:
    token = os.environ.get("SLACK_USER_TOKEN")
    if not token:
        raise SystemExit("Missing SLACK_USER_TOKEN environment variable")

    client = WebClient(token=token)

    try:
        resp = client.reminders_list()
    except SlackApiError as e:
        err = e.response.get("error") if hasattr(e, "response") else str(e)
        raise SystemExit(f"Slack API error: {err}")

    reminders = resp.get("reminders", []) or []

    events = []
    for r in reminders:
        if not isinstance(r, dict):
            continue
        if r.get("complete_ts"):
            continue

        t = r.get("time")
        if not isinstance(t, int):
            continue

        events.append(
            {
                "id": r.get("id"),
                "title": r.get("text") or "Reminder",
                "start": ts_to_iso_local(t),
                "allDay": False,
            }
        )

    EVENTS_FILE.write_text(json.dumps(events, indent=2), encoding="utf-8")
    print(f"Wrote {len(events)} reminder(s) to {EVENTS_FILE}")


if __name__ == "__main__":
    main()
