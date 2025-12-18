from __future__ import annotations

import datetime as dt
import os
import random
from pathlib import Path
from typing import Any
import requests

import streamlit as st

try:
    # FullCalendar wrapper for Streamlit (interactive month/week/day grid)
    from streamlit_calendar import calendar
except Exception:  # pragma: no cover
    calendar = None

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except Exception:  # pragma: no cover
    WebClient = None
    SlackApiError = Exception

try:
    # Optional helper component for timed reruns
    from streamlit_autorefresh import st_autorefresh
except Exception:  # pragma: no cover
    st_autorefresh = None


APP_NAME = "MoMents"
REPOSITORY_DIR = Path(__file__).with_name("repository")

MOTIVATIONAL_QUOTES = [
    "Small progress is still progress.",
    "Start where you are. Use what you have. Do what you can.",
    "Consistency beats intensity.",
    "Done is better than perfect.",
    "One step at a time — you’ve got this.",
    "Focus on the next right thing.",
    "Your future self will thank you.",
    "Keep going — momentum is everything.",
    "Make it work, then make it better.",
    "Today’s effort is tomorrow’s results.",
]


def _get_slack_user_token() -> str | None:
    # Prefer Streamlit secrets, then environment.
    # Streamlit secrets: .streamlit/secrets.toml => SLACK_USER_TOKEN="xoxp-..." (or xoxc-...)
    token = None
    try:
        token = st.secrets.get("SLACK_USER_TOKEN")  # type: ignore[attr-defined]
    except Exception:
        token = None

    if token:
        return str(token)

    token = os.environ.get("SLACK_USER_TOKEN")
    return token or None


def _ts_to_iso_local(ts: int) -> str:
    # Slack reminder 'time' is a unix epoch timestamp (seconds).
    # Convert to local time with timezone offset for FullCalendar.
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).astimezone().isoformat()


def _fetch_slack_reminders(token: str) -> tuple[list[dict[str, Any]], str | None]:
    if WebClient is None:
        return [], "Missing dependency 'slack_sdk'. Install from requirements.txt."

    try:
        client = WebClient(token=token)
        resp = client.reminders_list()
        reminders = resp.get("reminders", []) or []
        parsed = [r for r in reminders if isinstance(r, dict)]
        return parsed, None

    except SlackApiError as e:  # type: ignore[misc]
        err = None
        try:
            err = e.response.get("error")
        except Exception:
            err = str(e)
        return [], f"Slack API error: {err}"
    except Exception as e:
        return [], f"Failed to fetch Slack reminders: {e}"


def _fetch_slack_reminders_as_events(token: str) -> tuple[list[dict[str, Any]], str | None]:
    reminders, err = _fetch_slack_reminders(token)
    if err:
        return [], err

    events: list[dict[str, Any]] = []
    for r in reminders:
        text = r.get("text") or "Reminder"
        rid = r.get("id")

        t = r.get("time")
        if not isinstance(t, int):
            continue

        # Skip completed reminders for calendar view.
        if r.get("complete_ts"):
            continue

        events.append(
            {
                "id": rid,
                "title": str(text),
                "start": _ts_to_iso_local(t),
                "allDay": False,
            }
        )

    return events, None


def _complete_slack_reminder(token: str, reminder_id: str) -> tuple[bool, str | None]:
    if WebClient is None:
        return False, "Missing dependency 'slack_sdk'. Install from requirements.txt."

    try:
        client = WebClient(token=token)
        # Requires scope reminders:write
        client.reminders_complete(reminder=reminder_id)
        return True, None

    except SlackApiError as e:  # type: ignore[misc]
        err = None
        try:
            err = e.response.get("error")
        except Exception:
            err = str(e)
        return False, f"Slack API error: {err}"
    except Exception as e:
        return False, f"Failed to complete reminder: {e}"


def set_page(page: str) -> None:
    st.session_state["page"] = page


def _ensure_repository_dir() -> None:
    REPOSITORY_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", " ") else "" for ch in name).strip()
    cleaned = "_".join(cleaned.split())
    return cleaned or "summary"


def save_summary_to_repository(*, title: str, summary: str, source_type: str, source_name: str | None) -> Path:
    _ensure_repository_dir()

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{ts}_{_safe_filename(title)}.md"
    path = REPOSITORY_DIR / fname

    header = [
        f"# {title}",
        "",
        f"- Created: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"- Source type: {source_type}",
        f"- Source name: {source_name or 'N/A'}",
        "",
        "---",
        "",
    ]

    path.write_text("\n".join(header) + summary.strip() + "\n", encoding="utf-8")
    return path


def list_repository_items() -> list[Path]:
    _ensure_repository_dir()
    items = [p for p in REPOSITORY_DIR.glob("*.md") if p.is_file()]
    return sorted(items, key=lambda p: p.stat().st_mtime, reverse=True)


def init_state() -> None:
    if "page" not in st.session_state:
        st.session_state["page"] = "home"


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(f"## {APP_NAME}")
        st.caption("Navigation")

        st.button("🏠 Home", use_container_width=True, on_click=set_page, args=("home",), key="sb_home")
        st.button(
            "📁 Repository",
            use_container_width=True,
            on_click=set_page,
            args=("repository",),
            key="sb_repository",
        )
        st.button(
            "✅ Status",
            use_container_width=True,
            on_click=set_page,
            args=("status",),
            key="sb_status",
        )

        st.divider()
        st.caption("Motivation")
        quote = random.choice(MOTIVATIONAL_QUOTES)
        st.markdown(
            f"""
<div style="
  padding: 0.9rem 0.95rem;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.92);
  box-shadow: 0 10px 30px rgba(0,0,0,0.28);
">
  <div style="font-size: 0.95rem; line-height: 1.35;">
    “{quote}”
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )


def render_header(title: str) -> None:
    st.markdown(f"# {APP_NAME} — {title}")


def inject_global_css() -> None:
    # Scoped styles (we wrap the Home page buttons in a .moments-home div)
    st.markdown(
        """
<style>
/* App-wide aesthetic */
.stApp {
  background: radial-gradient(1200px 700px at 15% 10%, rgba(109, 40, 217, 0.25), rgba(0,0,0,0)),
              radial-gradient(900px 600px at 85% 0%, rgba(6, 182, 212, 0.20), rgba(0,0,0,0)),
              linear-gradient(180deg, #0B1220 0%, #0A0F1A 100%);
}

/* Make content feel like a centered “glass” panel */
section.main > div.block-container {
  padding-top: 2.2rem;
  padding-bottom: 3rem;
}

/* Center & style the title */
.stApp h1 {
  text-align: center;
  font-weight: 850;
  letter-spacing: 0.3px;
  background: linear-gradient(90deg, #A78BFA 0%, #60A5FA 40%, #22D3EE 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}


/* Home page hero */
.moments-hero {
  text-align: center;
  margin: 0.2rem 0 1.4rem 0;
}
.moments-hero p {
  color: rgba(255, 255, 255, 0.78);
  font-size: 1.05rem;
  margin: 0;
}

/* Make the 3 buttons dominate the homepage */
.moments-home {
  margin-top: 2.2rem;
  margin-bottom: 1.5rem;
}

.moments-home .stButton > button {
  height: 11.5rem;              /* big cards */
  width: 100%;
  padding: 1.2rem 1.3rem;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: linear-gradient(135deg, #6D28D9 0%, #2563EB 45%, #06B6D4 100%);
  color: #ffffff;
  font-weight: 850;
  font-size: 1.55rem;
  letter-spacing: 0.2px;
  box-shadow: 0 18px 60px rgba(0, 0, 0, 0.30);
  transition: transform 110ms ease-in-out, box-shadow 110ms ease-in-out, filter 110ms ease-in-out;
}

/* Give each column a slightly different accent */
.moments-home .moments-btn-1 .stButton > button {
  background: linear-gradient(135deg, #7C3AED 0%, #2563EB 55%, #22D3EE 100%);
}
.moments-home .moments-btn-2 .stButton > button {
  background: linear-gradient(135deg, #F97316 0%, #EF4444 55%, #A855F7 100%);
}
.moments-home .moments-btn-3 .stButton > button {
  background: linear-gradient(135deg, #10B981 0%, #22C55E 45%, #06B6D4 100%);
}

.moments-home .stButton > button:hover {
  transform: translateY(-4px);
  box-shadow: 0 26px 80px rgba(0, 0, 0, 0.36);
  filter: brightness(1.04);
}
.moments-home .stButton > button:active {
  transform: translateY(0px) scale(0.99);
}
.moments-home .stButton > button p {
  margin: 0;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_home() -> None:
    render_header("Home")

    st.markdown(
        """
<div class="moments-hero">
  <p><b>Welcome to MoMents.</b> Create summaries, manage reminders, and view your calendar.</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="moments-home">', unsafe_allow_html=True)

    # Make the buttons occupy the majority of the homepage.
    # Use nearly-full width, with a small outer margin.
    outer_l, outer_c, outer_r = st.columns([0.25, 9.5, 0.25])
    with outer_c:
        c1, c2, c3 = st.columns(3, gap="large")

        with c1:
            st.markdown('<div class="moments-btn-1">', unsafe_allow_html=True)
            st.button(
                "📝  Summarise",
                use_container_width=True,
                on_click=set_page,
                args=("summarise",),
                key="home_summarise",
            )
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="moments-btn-2">', unsafe_allow_html=True)
            st.button(
                "🔔  Notifications",
                use_container_width=True,
                on_click=set_page,
                args=("notifications",),
                key="home_notifications",
            )
            st.markdown("</div>", unsafe_allow_html=True)

        with c3:
            st.markdown('<div class="moments-btn-3">', unsafe_allow_html=True)
            st.button(
                "📅  Calendar",
                use_container_width=True,
                on_click=set_page,
                args=("calendar",),
                key="home_calendar",
            )
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_summarise() -> None:
    render_header("Summarise")

    st.button("← Back to Home", on_click=set_page, args=("home",))
    st.divider()

    st.subheader("Where is the content coming from?")
    source = st.radio(
        "Select a source type",
        options=["Text file", "Audio file", "Video file"],
        horizontal=True,
    )

    uploaded = None
    if source == "Text file":
        uploaded = st.file_uploader(
            "Upload a text file",
            type=["txt", "md", "csv"],
            accept_multiple_files=False,
        )
    elif source == "Audio file":
        uploaded = st.file_uploader(
            "Upload an audio file",
            type=["mp3", "wav", "m4a", "aac", "ogg"],
            accept_multiple_files=False,
        )
    else:
        uploaded = st.file_uploader(
            "Upload a video file",
            type=["mp4", "mov", "mkv", "avi", "webm"],
            accept_multiple_files=False,
        )

    st.info("Summarisation logic will be added later.")


def render_notifications() -> None:
    render_header("Notifications")

    st.button("← Back to Home", on_click=set_page, args=("home",))
    st.divider()

    st.info("Notification logic will be added later.")


def render_repository() -> None:
    render_header("Repository")

    st.button("← Back to Home", on_click=set_page, args=("home",))
    st.divider()

    items = list_repository_items()
    if not items:
        st.info("No summaries saved yet.")
        return

    labels = [p.name for p in items]
    chosen = st.selectbox("Saved summaries", options=labels)
    selected = REPOSITORY_DIR / chosen

    st.caption(f"Stored in: {selected}")
    st.markdown(selected.read_text(encoding="utf-8"))


def render_status() -> None:
    render_header("Status")

    st.button("← Back to Home", on_click=set_page, args=("home",))
    st.divider()

    st.subheader("Slack Reminders — To Do")
    st.caption("Mark items complete to strike them off.")

    token_from_env = _get_slack_user_token() or ""
    token = st.text_input(
        "Slack user token (xoxp-/xoxc-)",
        value=st.session_state.get("slack_token") or token_from_env,
        type="password",
        help="To mark reminders complete, the token must have `reminders:write` in addition to `reminders:read`.",
        key="status_slack_token",
    )

    # Keep the token in session so Calendar can reuse it.
    st.session_state["slack_token"] = token

    if not token:
        st.info("Add `SLACK_USER_TOKEN` (or paste a token above) to load your reminders.")
        return

    reminders, err = _fetch_slack_reminders(token)
    if err:
        st.error(err)
        return

    incomplete: list[dict[str, Any]] = [r for r in reminders if not r.get("complete_ts")]
    complete: list[dict[str, Any]] = [r for r in reminders if r.get("complete_ts")]

    if not incomplete and not complete:
        st.info("No reminders found in Slack.")
        return

    # Sort by upcoming time if available
    def _rem_time(r: dict[str, Any]) -> int:
        t = r.get("time")
        return int(t) if isinstance(t, int) else 0

    incomplete.sort(key=_rem_time)
    complete.sort(key=_rem_time, reverse=True)

    st.markdown("#### To do")
    any_selected = False
    selected_ids: list[str] = []

    for r in incomplete:
        rid = r.get("id")
        if not isinstance(rid, str) or not rid:
            continue

        text = str(r.get("text") or "Reminder")
        t = r.get("time")
        when = ""
        if isinstance(t, int):
            when = dt.datetime.fromtimestamp(t, tz=dt.timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")

        checked = st.checkbox(
            f"{text}" + (f"  —  {when}" if when else ""),
            value=False,
            key=f"status_done_{rid}",
        )
        if checked:
            any_selected = True
            selected_ids.append(rid)

    col_a, col_b = st.columns([2, 1])
    with col_a:
        if st.button("Mark selected as completed", use_container_width=True, disabled=not any_selected):
            errors: list[str] = []
            for rid in selected_ids:
                ok, e = _complete_slack_reminder(token, rid)
                if not ok and e:
                    errors.append(f"{rid}: {e}")
                # clear checkbox state so it doesn't stay checked
                st.session_state.pop(f"status_done_{rid}", None)

            if errors:
                st.error("\n".join(errors))
            st.rerun()

    with col_b:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    if complete:
        st.divider()
        st.markdown("#### Completed")
        for r in complete:
            text = str(r.get("text") or "Reminder")
            st.markdown(f"- ~~{text}~~")

def render_calendar() -> None:
    render_header("Calendar")

    st.button("← Back to Home", on_click=set_page, args=("home",))
    st.divider()

    st.caption("Interactive Month/Week/Day calendar.")

    if calendar is None:
        st.error(
            "Interactive calendar component is missing. Run: `pip install -r requirements.txt` "
            "and restart `streamlit run app.py`."
        )
        return

    left, right = st.columns([1, 2])

    with left:
        st.subheader("Slack reminders")
        st.markdown(
            "Slack reminders are fetched via `reminders.list` and require a **user token** "
            "with scope `reminders:read` (not a bot token)."
        )

        token_from_env = _get_slack_user_token() or ""
        token = st.text_input(
            "Slack user token (xoxp-/xoxc-)",
            value=token_from_env,
            type="password",
            help="Prefer setting SLACK_USER_TOKEN in Streamlit secrets or an environment variable.",
        )

        st.session_state["slack_token"] = token

        auto_refresh = st.checkbox(
            "Auto-refresh Slack reminders",
            value=False,
            key="slack_auto_refresh",
            help="Periodically re-sync reminders from Slack.",
        )
        interval_s = st.selectbox(
            "Refresh interval",
            options=[15, 30, 60, 300],
            index=2,
            key="slack_refresh_interval_s",
            disabled=not auto_refresh,
            help="Choose a safe interval to avoid hitting Slack rate limits.",
        )

        if auto_refresh:
            if st_autorefresh is None:
                st.warning(
                    "Auto-refresh component not installed. Install dependencies from `requirements.txt` and restart."
                )
            else:
                # interval is milliseconds
                st_autorefresh(interval=int(interval_s * 1000), key="slack_autorefresh")

        if st.button("Sync from Slack", use_container_width=True):
            if not token:
                st.error("Set SLACK_USER_TOKEN (or paste a token) before syncing.")
            else:
                events, err = _fetch_slack_reminders_as_events(token)
                if err:
                    st.error(err)
                else:
                    st.session_state["slack_events"] = events
                    st.success(f"Loaded {len(events)} reminder(s) from Slack.")

    with right:
        # Prefer token typed into the UI (stored in session), otherwise secrets/env.
        token = st.session_state.get("slack_token") or _get_slack_user_token()

        # If auto-refresh is enabled, fetch on every rerun; otherwise, use cached session events.
        auto_refresh_enabled = bool(st.session_state.get("slack_auto_refresh"))

        if auto_refresh_enabled and token:
            events, err = _fetch_slack_reminders_as_events(str(token))
            if err:
                st.warning(err)
                events = []
            else:
                st.session_state["slack_events"] = events
        elif isinstance(st.session_state.get("slack_events"), list):
            events = st.session_state.get("slack_events")
        elif token:
            events, err = _fetch_slack_reminders_as_events(str(token))
            if err:
                st.warning(err)
                events = []
            else:
                st.session_state["slack_events"] = events
        else:
            events = []

        if not token and not events:
            st.info("Add `SLACK_USER_TOKEN` (or paste a token on the left) to load reminders.")

        options = {
            "initialView": "dayGridMonth",
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek,timeGridDay",
            },
            # External source is the "source of truth" for reminders.
            "editable": False,
            "selectable": False,
            "navLinks": True,
            "nowIndicator": True,
            "weekNumbers": True,
            "height": "auto",
        }

        calendar(events=events, options=options, key="moments_calendar")


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="📝", layout="wide")
    inject_global_css()
    init_state()
    render_sidebar()

    page = st.session_state["page"]

    if page == "home":
        render_home()
    elif page == "summarise":
        render_summarise()
    elif page == "notifications":
        render_notifications()
    elif page == "repository":
        render_repository()
    elif page == "status":
        render_status()
    elif page == "calendar":
        render_calendar()
    else:
        set_page("home")
        st.rerun()


if __name__ == "__main__":
    main()
