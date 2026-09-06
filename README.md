# Household Budget (Streamlit)

Personal categories sit with one person, shared categories split by an adjustable
percentage, and each balance is income minus (own costs + share of shared costs).

## Run it locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

With no secrets configured it falls back to `local_store.json` so you can try it
immediately. That fallback is for your laptop only — see below.

## Why it needs a Google Sheet

Streamlit Community Cloud wipes the app's disk on every restart and puts apps to
sleep after 12 quiet hours. A budget you open once a month will sleep constantly,
so anything written to a local file will be gone by your next visit. The data has
to live outside the app, and a Google Sheet is free, never sleeps, and stays
readable if you ever want to check the numbers by hand.

### Setting it up

1. **Create a sheet.** New blank Google Sheet, any name. From the URL
   `docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`, copy the ID.
   Leave it empty — the app creates the `categories`, `settings`, and
   `transactions` tabs and seeds your existing budget on first run.

2. **Make a service account.** In the Google Cloud Console: new project →
   APIs & Services → enable **Google Sheets API** → Credentials →
   Create credentials → Service account. Then Keys → Add key → JSON, and
   download it.

3. **Share the sheet with the robot.** Open the JSON, copy the `client_email`
   (ends in `.iam.gserviceaccount.com`), and Share the sheet with that address
   as **Editor**. This step is the one people skip; without it you get
   `SpreadsheetNotFound`.

4. **Add the secrets.** Copy `.streamlit/secrets.toml.example` to
   `.streamlit/secrets.toml` and fill in `sheet_id` plus the JSON fields.
   Keep the `private_key` on one line with the `\n` escapes intact.
   The real `secrets.toml` is gitignored — never commit it.

## Deploy

```bash
git init && git add . && git commit -m "Household budget"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/budget-streamlit.git
git push -u origin main
```

Then at share.streamlit.io: **Create app** → pick the repo, branch `main`,
main file `streamlit_app.py` → **Advanced settings** → paste the contents of
your `secrets.toml` into the Secrets box → Deploy.

You get a `*.streamlit.app` URL. Note that on the free tier the app is publicly
reachable by default unless you restrict viewers in app settings, so set that
before you share the link.

## Day to day

- **Post fixed items** on the dashboard creates entries for everything marked
  Fixed — rent, loans, subscriptions, the parking income — so you only hand-enter
  the variable spending.
- **Reload from source** in the sidebar pulls fresh data. The app caches on load,
  so if you're both editing at once, hit that to see the other's entries.
- **Budget tab** edits categories in place. Direction decides the maths:
  *out* counts against the budget, *in* adds to income.

## Files

```
streamlit_app.py   the UI - dashboard, ledger, budget editor
store.py           storage backends; swap here for Postgres later
defaults.py        the seed budget used on first run
```
