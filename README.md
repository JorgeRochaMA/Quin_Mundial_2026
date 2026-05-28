# Quiniela Mundial 2026

Participa en la Quiniela Mundial 2026, captura tus marcadores, compite con tus amigos y sigue el ranking en vivo durante la fase de grupos.

The user-facing app is in Spanish. Code, comments, and technical documentation are in English.

## Features

- Login/register with nickname and shared access code.
- Multiple entries per user.
- Entry-based rankings.
- Match predictions with winner/draw and exact score.
- Dynamic prize pool using active entries.
- Admin panel for official results and prize pool configuration.
- Google Sheets backend with simple, editable tabs.

## Tech Stack

- Python
- Streamlit
- Pandas
- Google Sheets
- gspread
- google-auth

No Docker, Kubernetes, React, Next.js, or complex backend framework is required.

## Repository Structure

```text
app/
  app.py
  pages/
  components/
  services/
  utils/
  data/
  assets/
.streamlit/
  config.toml
  secrets.example.toml
tests/
requirements.txt
README.md
.gitignore
```

## Google Sheets Schema

Create one Google Spreadsheet and share it with your Google Cloud service account email as Editor.

The app can create missing tabs and headers automatically, but these are the expected tabs:

### CONFIG

| key | value |
| --- | --- |
| entry_fee | 200 |
| points_result | 3 |
| points_exact | 2 |
| first_place_percentage | 0.60 |
| second_place_percentage | 0.30 |
| third_place_percentage | 0.10 |
| lock_minutes_before_match | 60 |
| predictions_lock_at | 2026-06-10 23:59 |
| current_phase_label | Fase de grupos |
| current_phase_total_matches | 72 |
| current_phase_groups | 12 |
| pool_access_code | set-your-user-code |
| admin_access_code | set-your-admin-code |
| timezone | America/Mexico_City |

The app creates these keys with empty values on first run. Set both access codes in Google Sheets before sharing the app.

### USERS

`user_id`, `full_name`, `nickname`, `email`, `role`, `active`

`role` is an MVP extension used to distinguish `USER` and `ADMIN`.

### ENTRIES

`entry_id`, `user_id`, `entry_name`, `paid`, `amount_paid`, `created_at`, `active`

`paid` and `amount_paid` are kept for schema compatibility, but the current MVP assumes every created entry is paid. The prize pool uses active entries.

### MATCHES

`match_id`, `stage`, `group`, `match_date`, `home_team`, `away_team`, `stadium`, `city`, `status`

Supported status values:

- `OPEN`
- `LOCKED`
- `FINISHED`

### RESULTS

`match_id`, `home_score`, `away_score`, `updated_at`

### PREDICTIONS

`prediction_id`, `entry_id`, `match_id`, `selected_result`, `pred_home_goals`, `pred_away_goals`, `points`, `submitted_at`

Supported `selected_result` values:

- `HOME_WIN`
- `AWAY_WIN`
- `DRAW`

## Local Setup

1. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create Google Cloud service account credentials:

- Go to Google Cloud Console.
- Create a project or use an existing one.
- Enable the Google Sheets API.
- Create a service account.
- Create a JSON key.
- Copy the service account email.

4. Prepare Google Sheets:

- Create a Google Spreadsheet.
- Share it with the service account email as Editor.
- Copy the spreadsheet ID from the URL.

5. Configure Streamlit secrets:

```bash
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
```

Fill `.streamlit/secrets.toml` with the spreadsheet ID and service account JSON fields.

6. Run the app:

```bash
streamlit run app/app.py
```

The first run validates or creates the required worksheet tabs.

## Local Design Preview Without Google Sheets

Use demo mode when you only want to review the UI and make design changes without configuring Google Sheets yet.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
QUINIELA_DATA_SOURCE=demo streamlit run app/app.py
```

Demo login:

- User preview: nickname `George`, access code `demo-user`
- Admin preview: nickname `Admin`, access code `demo-admin`

Demo mode stores data only in the current browser session. Use it for local previews only, not for deployment.

## Static HTML Preview

If you only want to review the visual direction without running Streamlit, open:

```text
preview/index.html
```

This file is a static design prototype. It does not connect to Google Sheets and does not replace the Streamlit app.

## Loading Matches

Use `app/data/sample_matches.csv` as a template for the `MATCHES` tab.

Replace sample rows with the official match schedule you want to use. Keep `match_id` stable, because predictions and results depend on it.

Recommended `match_date` format:

```text
2026-06-11 20:00
```

## Scoring Rules

- Correct winner/draw: 3 points.
- Exact score: +2 points.
- Maximum per match: 5 points.

Example:

Official result: Mexico 2-1 Japan

- Prediction 2-1: 5 points.
- Prediction 1-0: 3 points.
- Prediction 1-1: 0 points.

## Prize Rules

Prize pool:

```text
active entries * entry fee
```

Default distribution:

- 1st place: 60%
- 2nd place: 30%
- 3rd place: 10%

These values can be changed in the `CONFIG` tab.

The dashboard uses `current_phase_total_matches` to show total, played, and remaining matches for the current pool phase. For the initial MVP, the pool is configured for the 72-match group stage. The `predictions_lock_at` value controls the pool-wide cutoff for editing predictions.

## Admin Flow

1. Log in with the admin access code.
2. Open `Admin`.
3. Update a match result.
4. Save.
5. The app writes the result to Google Sheets, marks the match as `FINISHED`, recalculates prediction points, and refreshes the app.

Admins can also update the entry fee and prize percentages from the app. Prize percentages must add up to 100%.

## Streamlit Cloud Deployment

1. Push this repository to GitHub.
2. Go to Streamlit Cloud.
3. Create a new app from your GitHub repository.
4. Set the main file path:

```text
app/app.py
```

5. Add secrets in Streamlit Cloud using the same format as `.streamlit/secrets.example.toml`.
6. Deploy.

## GitHub Upload

From the repository root:

```bash
git init
git add .
git commit -m "Initial MVP for World Cup prediction pool"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

If this folder is already a Git repository, skip `git init`.

## Tests

Run lightweight business-logic tests with:

```bash
python -m unittest
```

## Notes for Future Scaling

- Replace shared access codes with per-user authentication.
- Add a proper audit log for admin changes.
- Add tie rules for prize payouts.
- Add automated match imports once the final schedule source is chosen.
- Add a persistent rankings snapshot if the sheet grows large.
