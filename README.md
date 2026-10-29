# Accessible Banking Companion — Combined Project

**INNOVEX | Dexathon 2026**

This folder combines the Flask backend, HTML templates, CSS/JavaScript frontend, SQLite database schema/database file, automated tests, development dependencies, deployment files, security guide, and an included SVG logo.

## Important safety boundary

This is an **educational demonstration prototype**, not a real banking service. It does not connect to a bank, verify identity, read real balances, send real bank alerts, transfer real money, or pay bills. Balances and transactions are fictional. Use only fictional test information. Never enter real banking passwords, PINs, OTPs, account numbers, or identity documents.

## Included

- `app.py` — Flask backend and database initialization
- `templates/` — HTML frontend pages
- `static/style.css` and `static/app.js` — styling and browser functionality
- `static/images/logo.svg` — included placeholder brand logo; replace this with your own logo if you have a separate image
- `banking_companion.db` — empty demonstration SQLite database with the expected tables
- `tests/test_app.py` — automated Flask tests
- `requirements.txt`, `requirements-dev.txt` — dependencies
- `.env.example` — environment-variable template
- `Procfile` — production server command
- `DEPLOYMENT_SECURITY_GUIDE.md` — deployment and security checklist

## Run on Windows

1. Install Python 3.10 or newer.
2. Extract the ZIP.
3. Open Command Prompt in the `accessible_banking_complete` folder.
4. Create and activate a virtual environment:

   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   ```

5. Install dependencies:

   ```bat
   python -m pip install -r requirements-dev.txt
   ```

6. Start the app:

   ```bat
   python app.py
   ```

7. Open `http://127.0.0.1:5000` in your browser.

You can also use `run_windows.bat` after installing dependencies.

## Run automated tests

With the virtual environment activated:

```bat
python -m pytest -q
```

Review and fix any failing tests before deployment. Test output can vary with your Python/package versions.

## Database

The app initializes the required SQLite tables on startup. By default, it uses `banking_companion.db` in this folder. To use a different path, set `BANKING_DB_PATH` as an environment variable. Keep SQLite on persistent storage when hosted; do not rely on an ephemeral deployment filesystem. The supplied database contains no users or real customer information.

## Production and security

- Set a strong, persistent `SECRET_KEY` using the host's secret/environment settings. Do not commit it to source control.
- Set `COOKIE_SECURE=1` only when serving the site over HTTPS.
- Configure persistent storage for SQLite, or use a managed database if the host or concurrency requirements call for it.
- Do not upload `.env`, secrets, personal data, or real banking records to a public repository.
- Review `DEPLOYMENT_SECURITY_GUIDE.md` before deployment.
- Passing automated tests does not prove the app is secure or production-ready.

## Logo replacement

Replace `static/images/logo.svg` with your actual logo and update the image filename in `templates/base.html` if needed. Keep accessible alt text if the logo conveys information; the current logo is decorative because the adjacent site name provides the label.


## Project files and original program

This package uses the Flask app in `app.py` as the main web application, with HTML templates, CSS, JavaScript, SQLite, and your supplied Invisible Eyes logo. The original Streamlit Python program is preserved in `reference/original_streamlit_program.txt` for reference; it is a separate implementation and should not be run as the same `app.py` alongside Flask.
