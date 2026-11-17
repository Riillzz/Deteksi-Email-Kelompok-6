"""Konfigurasi MailGuard V2. Secrets dibaca dari env atau Streamlit secrets."""
from __future__ import annotations

import os
from typing import Any


def get_setting(name: str, default: Any = None) -> Any:
    value = os.getenv(name)
    if value not in (None, ""):
        return value
    try:
        import streamlit as st  # imported only when running the web app

        value = st.secrets.get(name, default)
        return value if value not in (None, "") else default
    except Exception:
        return default


def get_admin_password_hash() -> str | None:
    value = get_setting("ADMIN_PASSWORD_HASH")
    return str(value).strip() if value else None


def get_supabase_config() -> tuple[str | None, str | None]:
    url = get_setting("SUPABASE_URL")
    key = (
        get_setting("SUPABASE_SECRET_KEY")
        or get_setting("SUPABASE_SERVICE_ROLE_KEY")
        or get_setting("SUPABASE_KEY")
    )
    return (str(url).strip() if url else None, str(key).strip() if key else None)
