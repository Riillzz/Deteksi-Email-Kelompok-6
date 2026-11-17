"""Uji mandiri model, database lokal, kode pelacakan, dan login admin."""
from __future__ import annotations

import csv
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from database import (
    delete_message,
    get_counts,
    get_message_by_tracking_hash,
    init_db,
    list_messages,
    save_message,
)
from predictor import load_artifacts, predict_email
from security import (
    create_admin_password_hash,
    generate_tracking_code,
    hash_tracking_code,
    verify_admin_password,
)

BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["MAILGUARD_DB_PATH"] = str(Path(temp_dir) / "self_test.db")
        init_db()
        model, vectorizer = load_artifacts(BASE_DIR)

        sample_path = BASE_DIR / "contoh_email_demo.csv"
        with sample_path.open("r", encoding="utf-8-sig", newline="") as file:
            samples = list(csv.DictReader(file))

        assert len(samples) == 8, "CSV contoh harus berisi 8 email."
        correct = 0
        for item in samples:
            prediction = predict_email(item["subject"], item["body"], model, vectorizer)
            expected = item["expected_label"]
            if prediction.label == expected:
                correct += 1
            else:
                raise AssertionError(
                    f"Prediksi tidak sesuai untuk {item['scenario']}: "
                    f"expected={expected}, actual={prediction.label}"
                )

        try:
            predict_email("", "   ", model, vectorizer)
            raise AssertionError("Input kosong seharusnya ditolak.")
        except ValueError:
            pass

        item = samples[0]
        prediction = predict_email(item["subject"], item["body"], model, vectorizer)
        tracking_code = generate_tracking_code()
        save_message(
            tracking_hash=hash_tracking_code(tracking_code),
            sender_name=item["sender_name"],
            sender_email=item["sender_email"],
            recipient_email=item["recipient_email"],
            subject=item["subject"],
            body=item["body"],
            predicted_label=prediction.label,
            spam_probability=prediction.spam_probability,
            ham_probability=prediction.ham_probability,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        found = get_message_by_tracking_hash(hash_tracking_code(tracking_code))
        assert found is not None and found["subject"] == item["subject"]
        assert get_counts()["total"] == 1
        assert len(list_messages("Inbox")) == 1
        delete_message(found["id"])
        assert get_counts()["total"] == 0

        stored_hash = create_admin_password_hash("mailguard-test-password-2026")
        assert verify_admin_password("mailguard-test-password-2026", stored_hash)
        assert not verify_admin_password("wrong-password", stored_hash)

        print("PASS: 8/8 email demo sesuai label yang diharapkan")
        print("PASS: input kosong ditolak")
        print("PASS: penyimpanan, lookup kode tracking, filter Inbox, dan delete")
        print("PASS: password admin PBKDF2 diverifikasi")
        print("Semua tes mandiri berhasil.")


if __name__ == "__main__":
    main()
