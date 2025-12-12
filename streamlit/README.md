# Streamlit deployment for TallySync

This folder contains a lightweight Streamlit UI for interacting with the TallySync API. It is helpful for quick demos or for deploying on [Streamlit Community Cloud](https://streamlit.io/cloud) without needing the React frontend.

## Features

- Email/password authentication against the Django API (`/api/v1/auth/login/`)
- Profile summary for the logged-in tenant
- Bank statement upload with support for existing bank accounts or a Tally ledger name
- Statement listing with parsing progress
- Transaction viewer for a selected statement

## Running locally

```bash
pip install -r streamlit/requirements.txt
TALLYSYNC_API_BASE_URL=http://localhost:8000/api/v1 streamlit run streamlit/app.py
```

If the backend is running on a different host or path, set `TALLYSYNC_API_BASE_URL` accordingly before starting Streamlit.

## Deploying to Streamlit Cloud

1. Push this repository to your Git provider.
2. Create a new Streamlit app and point it to `streamlit/app.py`.
3. Add a secret named `TALLYSYNC_API_BASE_URL` with the public URL of your backend (for example, `https://api.yourdomain.com/api/v1`).
4. Deploy—the app will automatically render the login form and API tools.

## Notes

- The upload flow matches `POST /api/v1/bank-statements/upload/`, which expects either an existing bank account ID or a Tally bank ledger name to auto-create an account.
- Statement and transaction data are displayed read-only; additional write actions (mapping, approvals) can be added later if needed.
