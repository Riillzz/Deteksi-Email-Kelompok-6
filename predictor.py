"""
Fungsi prediksi email spam untuk Prototype Kelompok 6.
Metode: TF-IDF + Logistic Regression (C=10).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib


# =========================================================
# KONFIGURASI PREPROCESSING
# =========================================================

THRESHOLD = 0.5

EMAIL_PATTERN = re.compile(
    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
    flags=re.IGNORECASE,
)

URL_PATTERN = re.compile(
    r"""
    \b(?:https?://|ftp://|www\.)[^\s<>"']+
    |
    (?<![@\w])\b
    (?:[a-z0-9-]+\.)+
    (?:com|net|org|edu|gov|mil|info|biz|co|id|uk|io|me|xyz|online|site|app)
    (?:/[^\s<>"']*)?
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)

NON_ASCII_PATTERN = re.compile(r"[^\x00-\x7F]")
WHITESPACE_PATTERN = re.compile(r"\s+")


# =========================================================
# HASIL PREDIKSI
# =========================================================

@dataclass(frozen=True)
class PredictionResult:
    label: str
    label_id: int
    spam_probability: float
    ham_probability: float


# =========================================================
# MEMUAT MODEL DAN TF-IDF
# =========================================================

def load_artifacts(
    base_dir: str | Path | None = None
) -> tuple[Any, Any]:

    root = (
        Path(base_dir)
        if base_dir is not None
        else Path(__file__).resolve().parent
    )

    model_path = (
        root
        / "models"
        / "logistic_regression_kelompok6.joblib"
    )

    vectorizer_path = (
        root
        / "models"
        / "tfidf_vectorizer_kelompok6.joblib"
    )

    missing_files = [
        str(path)
        for path in (model_path, vectorizer_path)
        if not path.is_file()
    ]

    if missing_files:
        raise FileNotFoundError(
            "File model tidak ditemukan: "
            + ", ".join(missing_files)
        )

    model = joblib.load(model_path)
    vectorizer = joblib.load(vectorizer_path)

    return model, vectorizer


# =========================================================
# PENGGABUNGAN SUBJECT DAN MESSAGE
# =========================================================

def combine_email_text(
    subject: str | None,
    message: str | None
) -> str:

    subject_text = "" if subject is None else str(subject)
    message_text = "" if message is None else str(message)

    return f"{subject_text} {message_text}".strip()


# =========================================================
# PREPROCESSING TEXT
# =========================================================

def preprocess_text(text: str | None) -> str:
    """
    Tahapan preprocessing berdasarkan metodologi penelitian:

    1. Mengganti alamat email dengan emailtoken.
    2. Mengganti URL dengan urltoken.
    3. Mengubah huruf menjadi lowercase.
    4. Mengganti karakter non-ASCII dengan spasi.
    5. Normalisasi spasi.

    Stopwords tidak dihapus.
    Stemming tidak dilakukan.
    Angka dan tanda baca tidak dihapus secara agresif.
    """

    if text is None:
        return ""

    processed_text = str(text)

    # Mengganti alamat email
    processed_text = EMAIL_PATTERN.sub(
        " emailtoken ",
        processed_text
    )

    # Mengganti URL
    processed_text = URL_PATTERN.sub(
        " urltoken ",
        processed_text
    )

    # Mengganti karakter non-ASCII dengan spasi
    processed_text = NON_ASCII_PATTERN.sub(
        " ",
        processed_text
    )

    # Case folding
    processed_text = processed_text.lower()

    # Normalisasi spasi dan baris baru
    processed_text = WHITESPACE_PATTERN.sub(
        " ",
        processed_text
    ).strip()

    return processed_text


# =========================================================
# FUNGSI PREDIKSI EMAIL
# =========================================================

def predict_email(
    subject: str | None,
    message: str | None,
    model: Any,
    vectorizer: Any,
) -> PredictionResult:
    """
    Memprediksi email sebagai HAM atau SPAM.

    Input:
        subject : Subjek email
        message : Isi email

    Output:
        Label klasifikasi
        Probabilitas spam
        Probabilitas ham
    """

    # Menggabungkan subject dan message
    combined_text = combine_email_text(
        subject,
        message
    )

    # Preprocessing
    cleaned_text = preprocess_text(combined_text)

    # Validasi input kosong
    if not cleaned_text:
        raise ValueError("Masukan email kosong!")

    # Ekstraksi fitur TF-IDF
    features = vectorizer.transform([
        cleaned_text
    ])

    # Menghitung probabilitas
    probabilities = model.predict_proba(features)[0]

    # Menghubungkan probabilitas dengan label kelas
    class_probabilities = {
        int(class_id): float(probability)
        for class_id, probability in zip(
            model.classes_,
            probabilities
        )
    }

    if 0 not in class_probabilities or 1 not in class_probabilities:
        raise ValueError(
            "Model tidak memiliki kelas HAM (0) dan SPAM (1)."
        )

    ham_probability = class_probabilities[0]
    spam_probability = class_probabilities[1]

    # Threshold klasifikasi 0,5
    label_id = (
        1 if spam_probability >= THRESHOLD else 0
    )

    label = (
        "SPAM" if label_id == 1 else "HAM"
    )

    return PredictionResult(
        label=label,
        label_id=label_id,
        spam_probability=spam_probability,
        ham_probability=ham_probability,
    )