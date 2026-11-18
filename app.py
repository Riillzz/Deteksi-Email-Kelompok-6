from __future__ import annotations

from pathlib import Path

import streamlit as st

from predictor import load_artifacts, predict_email


# =========================================================
# KONFIGURASI APLIKASI
# =========================================================

APP_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Email Detection",
    page_icon="✉️",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .stApp {
        background-color: #f8fafc;
    }

    .block-container {
        max-width: 850px;
        padding-top: 2.5rem;
        padding-bottom: 3rem;
    }

    .main-title {
        font-size: 2.2rem;
        font-weight: 750;
        color: #1e293b;
        margin-bottom: 0.2rem;
    }

    .subtitle {
        color: #64748b;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }

    .section-title {
        font-size: 1.1rem;
        font-weight: 650;
        color: #334155;
    }

    div[data-testid="stForm"] {
        background-color: white;
        padding: 1.4rem;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
    }

    div.stButton > button,
    div.stFormSubmitButton > button {
        border-radius: 8px;
        font-weight: 600;
        min-height: 2.7rem;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea {
        border-radius: 8px;
    }

    .result-caption {
        color: #64748b;
        font-size: 0.85rem;
    }

    footer {
        visibility: hidden;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# MEMUAT MODEL
# =========================================================

@st.cache_resource(show_spinner="Memuat model klasifikasi email...")
def get_model_artifacts():
    return load_artifacts(APP_DIR)


try:
    model, vectorizer = get_model_artifacts()

except Exception:
    st.error(
        "Model tidak dapat dimuat. "
        "Pastikan folder models tersedia dan file model tidak berubah."
    )
    st.stop()


# =========================================================
# HEADER
# =========================================================

st.markdown(
    '<div class="main-title">Email Detection</div>',
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="subtitle">
        Prototype klasifikasi email untuk mendeteksi
        pesan spam dan ham menggunakan Machine Learning.
    </div>
    """,
    unsafe_allow_html=True
)

st.divider()


# =========================================================
# FORM INPUT EMAIL
# =========================================================

st.markdown(
    '<div class="section-title">Pemeriksaan Email</div>',
    unsafe_allow_html=True
)

st.write(
    "Masukkan subjek dan isi email yang ingin diperiksa."
)

with st.form(
    "email_detection_form",
    clear_on_submit=False
):

    subject = st.text_input(
        "Subject",
        placeholder="Masukkan subjek email...",
        max_chars=250
    )

    message = st.text_area(
        "Message",
        placeholder="Masukkan isi email...",
        height=230,
        max_chars=30000
    )

    submitted = st.form_submit_button(
        "Periksa Email",
        type="primary",
        use_container_width=True
    )


# =========================================================
# PROSES PREDIKSI
# =========================================================

if submitted:

    # Menghapus hasil prediksi sebelumnya
    st.session_state.pop(
        "last_prediction",
        None
    )

    try:

        # Prediksi email
        result = predict_email(
            subject=subject,
            message=message,
            model=model,
            vectorizer=vectorizer
        )

        # Menyimpan hasil prediksi di session
        st.session_state["last_prediction"] = {
            "label": result.label,
            "spam_probability": result.spam_probability,
            "ham_probability": result.ham_probability,
            "subject": subject.strip(),
        }

    except ValueError as error:

        st.error(str(error))

    except Exception:

        st.error(
            "Terjadi kesalahan ketika memproses email. "
            "Silakan periksa kembali input dan model."
        )


# =========================================================
# MENAMPILKAN HASIL
# =========================================================

prediction = st.session_state.get(
    "last_prediction"
)

if prediction:

    st.divider()

    st.markdown(
        '<div class="section-title">Hasil Klasifikasi</div>',
        unsafe_allow_html=True
    )

    label = prediction["label"]

    spam_probability = prediction[
        "spam_probability"
    ]

    ham_probability = prediction[
        "ham_probability"
    ]

    # Status hasil klasifikasi
    if label == "SPAM":

        st.error(
            "Email diklasifikasikan sebagai SPAM."
        )

    else:

        st.success(
            "Email diklasifikasikan sebagai HAM."
        )

    # Informasi hasil
    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            label="Hasil Prediksi",
            value=label
        )

    with col2:

        st.metric(
            label="Estimasi Probabilitas Spam",
            value=f"{spam_probability * 100:.2f}%"
        )

    # Visualisasi probabilitas spam
    st.write(
        "**Probabilitas Email Termasuk Spam**"
    )

    st.progress(
        int(spam_probability * 100)
    )

    st.caption(
        f"{spam_probability * 100:.2f}% kemungkinan spam"
    )

    # Probabilitas kedua kelas
    col3, col4 = st.columns(2)

    with col3:

        st.metric(
            "Probabilitas HAM",
            f"{ham_probability * 100:.2f}%"
        )

    with col4:

        st.metric(
            "Probabilitas SPAM",
            f"{spam_probability * 100:.2f}%"
        )

    # Informasi email yang diperiksa
    if prediction["subject"]:

        st.caption(
            f"Subject yang diperiksa: {prediction['subject']}"
        )

    else:

        st.caption(
            "Email tidak memiliki subject. "
            "Klasifikasi dilakukan berdasarkan isi pesan."
        )

    st.info(
        "Threshold klasifikasi yang digunakan adalah 0,5. "
        "Probabilitas merupakan estimasi keluaran model."
    )


# =========================================================
# INFORMASI METODE
# =========================================================

st.divider()

with st.expander(
    "Informasi Model dan Metode"
):

    st.markdown(
        """
        **Algoritma klasifikasi**

        Logistic Regression dengan konfigurasi model final:
        - Parameter C: 10,0
        - Regularisasi: L2
        - Solver: liblinear
        - Maksimum iterasi: 1000

        **Ekstraksi fitur**

        Term Frequency–Inverse Document Frequency (TF-IDF):
        - N-gram: Unigram
        - Maksimum fitur: 5.000
        - Minimum document frequency: 2
        - Normalisasi: L2
        - Stopwords: Tidak dihapus

        **Threshold klasifikasi**

        - HAM: Probabilitas spam di bawah 0,5.
        - SPAM: Probabilitas spam sama dengan atau di atas 0,5.

        **Dataset**

        Enron Spam Dataset dengan sampel penelitian sebanyak
        5.000 email berbahasa Inggris.
        """
    )


# =========================================================
# KETERBATASAN MODEL
# =========================================================

st.warning(
    """
    **Catatan:** Model dilatih menggunakan dataset email
    berbahasa Inggris. Oleh karena itu, hasil klasifikasi
    pada email berbahasa Indonesia belum tentu akurat.
    Hasil prediksi juga bukan jaminan bahwa email aman
    atau berbahaya.
    """
)


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Email Detection | Project Machine Learning | Kelompok 6"
)