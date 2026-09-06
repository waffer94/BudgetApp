"""Storage for the budget app.

Two interchangeable backends:

  SheetsStore  - a Google Sheet, used whenever secrets are configured.
                 Survives Community Cloud restarts and lets both of you
                 read the same numbers.
  LocalStore   - a JSON file next to the app, for running on your laptop.
                 Do NOT rely on this in the cloud; the disk gets wiped.

Both expose the same six methods, so swapping in Postgres later means
writing one more class and nothing else.
"""

from __future__ import annotations

import json
import os
import uuid

import streamlit as st

import defaults

CAT_COLS = ["id", "name", "owner", "flow", "type", "budget", "fixed"]
TXN_COLS = ["id", "date", "kind", "cat_id", "who", "amount", "note"]
SET_COLS = ["key", "value"]

CAT_WS, TXN_WS, SET_WS = "categories", "transactions", "settings"


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def _bool(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes", "y")


def _num(v, default=0.0) -> float:
    try:
        return float(str(v).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------
# Google Sheets
# --------------------------------------------------------------------------
class SheetsStore:
    label = "Google Sheet"

    def __init__(self, sheet_id: str, creds_info: dict):
        import gspread
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_info(
            creds_info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        self.gc = gspread.authorize(creds)
        self.sh = self.gc.open_by_key(sheet_id)
        self._ensure_tabs()

    def _ws(self, title: str, cols: list[str]):
        try:
            return self.sh.worksheet(title)
        except Exception:
            ws = self.sh.add_worksheet(title=title, rows=200, cols=max(len(cols), 8))
            ws.update([cols], "A1")
            return ws

    def _ensure_tabs(self):
        cat = self._ws(CAT_WS, CAT_COLS)
        if len(cat.get_all_values()) <= 1:
            cat.update([CAT_COLS] + [
                [r["id"], r["name"], r["owner"], r["flow"], r["type"],
                 r["budget"], str(r["fixed"])]
                for r in defaults.CATEGORY_ROWS
            ], "A1")

        setts = self._ws(SET_WS, SET_COLS)
        if len(setts.get_all_values()) <= 1:
            setts.update(
                [SET_COLS] + [[k, str(v)] for k, v in defaults.SETTINGS.items()], "A1"
            )

        self._ws(TXN_WS, TXN_COLS)

    # -- reads ------------------------------------------------------------
    def read_categories(self) -> list[dict]:
        rows = self._ws(CAT_WS, CAT_COLS).get_all_records()
        return [
            {"id": str(r.get("id") or new_id()),
             "name": str(r.get("name", "")),
             "owner": str(r.get("owner", "common")),
             "flow": "in" if str(r.get("flow", "out")).lower() == "in" else "out",
             "type": str(r.get("type", "")),
             "budget": _num(r.get("budget")),
             "fixed": _bool(r.get("fixed"))}
            for r in rows if str(r.get("name", "")).strip()
        ]

    def read_settings(self) -> dict:
        rows = self._ws(SET_WS, SET_COLS).get_all_records()
        out = dict(defaults.SETTINGS)
        for r in rows:
            k = str(r.get("key", "")).strip()
            if k:
                out[k] = _num(r.get("value"))
        return out

    def read_txns(self) -> list[dict]:
        rows = self._ws(TXN_WS, TXN_COLS).get_all_records()
        return [
            {"id": str(r.get("id") or new_id()),
             "date": str(r.get("date", "")),
             "kind": str(r.get("kind", "expense")),
             "cat_id": str(r.get("cat_id", "") or ""),
             "who": str(r.get("who", "") or ""),
             "amount": _num(r.get("amount")),
             "note": str(r.get("note", "") or "")}
            for r in rows if str(r.get("date", "")).strip()
        ]

    # -- writes -----------------------------------------------------------
    def write_categories(self, cats: list[dict]):
        ws = self._ws(CAT_WS, CAT_COLS)
        body = [CAT_COLS] + [
            [c["id"], c["name"], c["owner"], c["flow"], c.get("type", ""),
             c["budget"], str(bool(c.get("fixed")))]
            for c in cats
        ]
        ws.clear()
        ws.update(body, "A1")

    def write_settings(self, settings: dict):
        ws = self._ws(SET_WS, SET_COLS)
        ws.clear()
        ws.update([SET_COLS] + [[k, str(v)] for k, v in settings.items()], "A1")

    def add_txns(self, rows: list[dict]):
        ws = self._ws(TXN_WS, TXN_COLS)
        ws.append_rows([[r.get(c, "") for c in TXN_COLS] for r in rows],
                       value_input_option="USER_ENTERED")

    def write_txns(self, rows: list[dict]):
        ws = self._ws(TXN_WS, TXN_COLS)
        ws.clear()
        ws.update([TXN_COLS] + [[r.get(c, "") for c in TXN_COLS] for r in rows], "A1")


# --------------------------------------------------------------------------
# Local JSON (development only)
# --------------------------------------------------------------------------
class LocalStore:
    label = "Local file"

    def __init__(self, path="local_store.json"):
        self.path = path
        if not os.path.exists(path):
            self._dump({
                "categories": defaults.CATEGORY_ROWS,
                "settings": defaults.SETTINGS,
                "transactions": [],
            })

    def _load(self) -> dict:
        with open(self.path) as f:
            return json.load(f)

    def _dump(self, data: dict):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def read_categories(self):
        return self._load()["categories"]

    def read_settings(self):
        return self._load()["settings"]

    def read_txns(self):
        return self._load()["transactions"]

    def write_categories(self, cats):
        d = self._load(); d["categories"] = cats; self._dump(d)

    def write_settings(self, settings):
        d = self._load(); d["settings"] = settings; self._dump(d)

    def add_txns(self, rows):
        d = self._load(); d["transactions"].extend(rows); self._dump(d)

    def write_txns(self, rows):
        d = self._load(); d["transactions"] = rows; self._dump(d)


@st.cache_resource(show_spinner="Connecting to your budget…")
def get_store():
    """Google Sheet when secrets are set, local file otherwise."""
    try:
        sheet_id = st.secrets["sheet_id"]
        creds = dict(st.secrets["gcp_service_account"])
        return SheetsStore(sheet_id, creds)
    except Exception:
        return LocalStore()
