"""Buat PBKDF2-SHA256 hash untuk ADMIN_PASSWORD_HASH tanpa menampilkan password."""
from __future__ import annotations

import getpass

from security import create_admin_password_hash


def main() -> None:
    password = getpass.getpass("Buat password admin baru: ")
    confirmation = getpass.getpass("Ulangi password admin: ")
    if len(password) < 12:
        raise SystemExit("Password minimal 12 karakter.")
    if password != confirmation:
        raise SystemExit("Password tidak sama.")
    print("\nSalin baris berikut ke .streamlit/secrets.toml atau Secrets di Streamlit Cloud:\n")
    print(f'ADMIN_PASSWORD_HASH = "{create_admin_password_hash(password)}"')


if __name__ == "__main__":
    main()
