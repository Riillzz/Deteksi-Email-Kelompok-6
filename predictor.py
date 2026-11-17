"""Inference helper untuk prototipe deteksi email spam Kelompok 6."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib


@dataclass(frozen=True)
class PredictionResult:
    label: str
    label_id: int
    spam_probability: float
    ham_probability: float


def load_artifacts(base_dir: str | Path | None = None) -> tuple[Any, Any]:
    """Load TF-IDF vectorizer dan Logistic Regression dari folder models."""
    root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent
    model_path = root / "models" / "logistic_regression_kelompok6.joblib"
    vectorizer_path = root / "models" / "tfidf_vectorizer_kelompok6.joblib"

    missing = [str(path) for path in (model_path, vectorizer_path) if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Artefak model tidak ditemukan: " + ", ".join(missing)
            + ". Pastikan folder models ikut disertakan."
        )

    model = joblib.load(model_path)
    vectorizer = joblib.load(vectorizer_path)
    return model, vectorizer


def combine_email_text(subject: str | None, message: str | None) -> str:
    """Samakan dengan preprocessing notebook: gabung teks dan normalisasi whitespace."""
    subject_text = "" if subject is None else str(subject)
    message_text = "" if message is None else str(message)
    return " ".join((subject_text + " " + message_text).split())


def predict_email(
    subject: str | None,
    message: str | None,
    model: Any,
    vectorizer: Any,
) -> PredictionResult:
    """Prediksi satu email; input kosong ditolak dengan ValueError."""
    combined_text = combine_email_text(subject, message)
    if not combined_text:
        raise ValueError("Email kosong. Masukkan subjek atau isi email terlebih dahulu.")

    features = vectorizer.transform([combined_text])
    label_id = int(model.predict(features)[0])
    probabilities = model.predict_proba(features)[0]
    class_to_probability = {
        int(class_id): float(probability)
        for class_id, probability in zip(model.classes_, probabilities)
    }

    return PredictionResult(
        label="SPAM" if label_id == 1 else "HAM",
        label_id=label_id,
        spam_probability=class_to_probability.get(1, 0.0),
        ham_probability=class_to_probability.get(0, 0.0),
    )
