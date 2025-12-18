# MoMents (DataSet_Hackathon)

Streamlit UI for MoMents with:
- Summarise (placeholder)
- Notifications (placeholder)
- Calendar (interactive month/week/day grid) powered by Slack Reminders

## Run
```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Slack setup
Set a Slack **user token** (xoxp-/xoxc-) with `reminders:read`.

### Option A: environment variable
```powershell
$env:SLACK_USER_TOKEN="xoxp-your-token"
```

### Option B: Streamlit secrets
Create `.streamlit/secrets.toml`:
```toml
SLACK_USER_TOKEN="xoxp-your-token"
```

> Note: `.streamlit/secrets.toml` is gitignored.
