"""Streamlit UI for interacting with the TallySync API."""
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional

import requests
import streamlit as st

API_BASE_URL = os.getenv("TALLYSYNC_API_BASE_URL", "http://localhost:8000/api/v1")
TIMEOUT = 30


def _build_url(path: str) -> str:
    return f"{API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def _auth_headers(token: Optional[str] = None) -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _request(  # noqa: PLR0913 - explicit arguments improve clarity for API calls
    method: str,
    path: str,
    token: Optional[str] = None,
    *,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
) -> requests.Response:
    url = _build_url(path)
    return requests.request(
        method,
        url,
        headers=_auth_headers(token),
        params=params,
        data=data,
        json=json,
        files=files,
        timeout=TIMEOUT,
    )


def login(email: str, password: str) -> Dict[str, str]:
    response = _request("post", "/auth/login/", json={"email": email, "password": password})
    response.raise_for_status()
    return response.json()


def fetch_profile(token: str) -> Dict[str, Any]:
    response = _request("get", "/auth/profile/", token=token)
    response.raise_for_status()
    return response.json()


def fetch_bank_accounts(token: str) -> List[Dict[str, Any]]:
    response = _request("get", "/bank-statements/accounts/", token=token)
    response.raise_for_status()
    return response.json()


def fetch_statements(token: str) -> List[Dict[str, Any]]:
    response = _request("get", "/bank-statements/", token=token)
    response.raise_for_status()
    return response.json()


def fetch_transactions(token: str, statement_id: int) -> List[Dict[str, Any]]:
    response = _request("get", f"/bank-statements/{statement_id}/transactions/", token=token)
    response.raise_for_status()
    return response.json()


def upload_statement(
    token: str,
    *,
    bank_account_id: Optional[int],
    bank_ledger_name: str,
    uploaded_file,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "bank_account": bank_account_id or "",
        "bank_ledger_name": bank_ledger_name,
    }
    files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
    response = _request("post", "/bank-statements/upload/", token=token, data=data, files=files)
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="TallySync Streamlit", page_icon="📊", layout="wide")

if "auth" not in st.session_state:
    st.session_state.auth = {"access": None, "refresh": None, "profile": None}

st.title("TallySync Streamlit Console")
st.caption("Interact with the TallySync API from Streamlit.")
st.info(
    "Using API base URL: **%s**. Set `TALLYSYNC_API_BASE_URL` to point to your deployed backend." % API_BASE_URL
)

with st.sidebar:
    st.header("Authentication")
    if st.session_state.auth.get("access"):
        profile = st.session_state.auth.get("profile") or {}
        st.success(f"Logged in as {profile.get('email', 'Unknown user')}")
        st.write(
            "**Tenant:**", profile.get("tenant", {}).get("schema_name", "-"),
            "| **Role:**", profile.get("role", "-"),
        )
        if st.button("Log out"):
            st.session_state.auth = {"access": None, "refresh": None, "profile": None}
            st.experimental_rerun()
    else:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in")
            if submitted:
                try:
                    tokens = login(email, password)
                    st.session_state.auth["access"] = tokens.get("access")
                    st.session_state.auth["refresh"] = tokens.get("refresh")
                    st.session_state.auth["profile"] = fetch_profile(tokens.get("access", ""))
                    st.success("Logged in successfully")
                    st.experimental_rerun()
                except requests.HTTPError as exc:  # pragma: no cover - Streamlit surface
                    st.error(f"Login failed: {exc.response.text}")
                except requests.RequestException as exc:  # pragma: no cover - Streamlit surface
                    st.error(
                        "Login failed: unable to reach the API at "
                        f"{API_BASE_URL}. Please verify the backend is running.\n{exc}"
                    )


def require_auth() -> Optional[str]:
    token = st.session_state.auth.get("access")
    if not token:
        st.warning("Please log in to access the API.")
        return None
    return token


def render_profile(token: str) -> None:
    st.subheader("Profile")
    profile = st.session_state.auth.get("profile") or fetch_profile(token)
    st.session_state.auth["profile"] = profile
    cols = st.columns(3)
    cols[0].metric("Email", profile.get("email", "-"))
    cols[1].metric("Role", profile.get("role", "-"))
    cols[2].metric("Tenant", profile.get("tenant", {}).get("schema_name", "-"))


@st.cache_data(show_spinner=False)
def cached_bank_accounts(token: str) -> List[Dict[str, Any]]:
    return fetch_bank_accounts(token)


@st.cache_data(show_spinner=False)
def cached_statements(token: str) -> List[Dict[str, Any]]:
    return fetch_statements(token)


def render_bank_upload(token: str) -> None:
    st.subheader("Upload bank statement")
    try:
        accounts = cached_bank_accounts(token)
    except requests.RequestException as exc:  # pragma: no cover - Streamlit surface
        st.error(
            "Unable to load bank accounts: unable to reach the API at "
            f"{API_BASE_URL}. Please verify the backend is running.\n{exc}"
        )
        return
    if accounts:
        account_labels = [f"{acc['bank_name']} ({acc['account_number']})" for acc in accounts]
        selected_index = st.selectbox(
            "Bank account",
            options=range(len(accounts)),
            format_func=lambda i: account_labels[i],
            index=0,
        )
        selected_account = accounts[selected_index]["id"]
    else:
        st.info("No bank accounts found yet—provide a Tally ledger name to auto-create one.")
        selected_account = None
    bank_ledger_name = st.text_input(
        "Tally bank ledger name (used if you don't have a bank account set up)",
        help="Either choose an existing bank account or supply a ledger name to auto-create one.",
    )
    uploaded_file = st.file_uploader("Upload PDF/Excel/CSV statement", type=["pdf", "xlsx", "xls", "csv"])
    if st.button("Upload statement"):
        if not uploaded_file:
            st.error("Please choose a file before uploading.")
            return
        if not selected_account and not bank_ledger_name:
            st.error("Select a bank account or provide a Tally ledger name so we know where to attach the statement.")
            return
        try:
            result = upload_statement(
                token,
                bank_account_id=selected_account,
                bank_ledger_name=bank_ledger_name,
                uploaded_file=uploaded_file,
            )
            st.success(result.get("message", "Uploaded"))
            st.json(result)
            cached_statements.clear()
        except requests.HTTPError as exc:  # pragma: no cover - Streamlit surface
            st.error(f"Upload failed: {exc.response.text}")
        except requests.RequestException as exc:  # pragma: no cover - Streamlit surface
            st.error(
                "Upload failed: unable to reach the API at "
                f"{API_BASE_URL}. Please verify the backend is running.\n{exc}"
            )


def _format_statements_table(statements: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for stmt in statements:
        rows.append(
            {
                "ID": stmt.get("id"),
                "Bank": stmt.get("bank_account"),
                "Status": stmt.get("status"),
                "Period": f"{stmt.get('period_start', '-')} → {stmt.get('period_end', '-')}",
                "Transactions": stmt.get("total_transactions", 0),
                "Mapped %": stmt.get("mapping_progress", 0),
                "Uploaded": stmt.get("uploaded_at"),
            }
        )
    return rows


def render_statements(token: str) -> Optional[int]:
    st.subheader("Bank statements")
    try:
        statements = cached_statements(token)
    except requests.RequestException as exc:  # pragma: no cover - Streamlit surface
        st.error(
            "Unable to load statements: unable to reach the API at "
            f"{API_BASE_URL}. Please verify the backend is running.\n{exc}"
        )
        return None
    if not statements:
        st.info("No statements found yet. Upload one to get started.")
        return None

    table_rows = _format_statements_table(statements)
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    statement_ids = [stmt["ID"] for stmt in table_rows]
    selected = st.selectbox("Choose a statement to inspect", options=statement_ids)
    return int(selected) if selected else None


def render_transactions(token: str, statement_id: int) -> None:
    st.subheader("Parsed transactions")
    try:
        transactions = fetch_transactions(token, statement_id)
        if not transactions:
            st.info("No transactions parsed for this statement yet.")
            return
        rows = []
        for txn in transactions:
            rows.append(
                {
                    "Date": txn.get("date"),
                    "Description": txn.get("description"),
                    "Debit": txn.get("debit"),
                    "Credit": txn.get("credit"),
                    "Suggested Ledger": txn.get("suggested_ledger_name"),
                    "Mapped Ledger": txn.get("mapped_ledger_name"),
                    "Status": txn.get("status"),
                    "Confidence": txn.get("confidence_score"),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
    except requests.HTTPError as exc:  # pragma: no cover - Streamlit surface
        st.error(f"Unable to load transactions: {exc.response.text}")
    except requests.RequestException as exc:  # pragma: no cover - Streamlit surface
        st.error(
            "Unable to load transactions: unable to reach the API at "
            f"{API_BASE_URL}. Please verify the backend is running.\n{exc}"
        )


def main() -> None:
    token = require_auth()
    if not token:
        return

    render_profile(token)
    st.divider()
    render_bank_upload(token)
    st.divider()
    statement_id = render_statements(token)
    if statement_id:
        render_transactions(token, statement_id)


if __name__ == "__main__":
    main()
