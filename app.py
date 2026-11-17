from __future__ import annotations

import csv
import html
import io
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from config import get_admin_password_hash
from database import (
    delete_message,
    get_backend_name,
    get_counts,
    get_message,
    get_message_by_tracking_hash,
    init_db,
    list_messages,
    save_message,
)
from predictor import load_artifacts, predict_email
from security import (
    generate_tracking_code,
    hash_tracking_code,
    verify_admin_password,
)


# =========================================================
# KONFIGURASI
# =========================================================

APP_DIR = Path(__file__).resolve().parent

EMAIL_RE = re.compile(
    r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
)

MAX_BODY_CHARS = 30000
MAX_SUBJECT_CHARS = 250


# =========================================================
# CONTOH EMAIL
# =========================================================

SAMPLES = {
    "Agenda rapat proyek": {
        "sender_name": "Alex Morgan",
        "sender_email": "alex.morgan@example.com",
        "recipient_email": "team@example.edu",
        "subject": "Project Meeting Agenda for Friday",
        "body": (
            "Dear team, please review the attached agenda before our "
            "project meeting on Friday at 10 AM. We will discuss the "
            "progress report and assign tasks for next week. Regards, Alex."
        ),
    },

    "Jadwal perkuliahan": {
        "sender_name": "Academic Office",
        "sender_email": "academic.office@example.edu",
        "recipient_email": "students@example.edu",
        "subject": "Updated Course Schedule",
        "body": (
            "Dear students, the updated lecture schedule for next week "
            "is now available. Please check the department website for "
            "room changes and contact the administration office if you "
            "have questions."
        ),
    },

    "Laporan proyek": {
        "sender_name": "Michael Brown",
        "sender_email": "michael.brown@example.com",
        "recipient_email": "john@example.com",
        "subject": "Quarterly Report Review",
        "body": (
            "Hi John, could you review the attached quarterly report "
            "before Thursday? Please add your comments to the shared "
            "document. Thank you."
        ),
    },

    "Undangan seminar": {
        "sender_name": "Research Office",
        "sender_email": "research.office@example.edu",
        "recipient_email": "faculty@example.edu",
        "subject": "Invitation to Research Seminar",
        "body": (
            "Dear colleagues, you are invited to attend the research "
            "seminar on Wednesday at 2 PM in Room 204. The speaker will "
            "present the latest project findings. Please register with "
            "the department secretary."
        ),
    },

    "Hadiah gratis": {
        "sender_name": "Lucky Rewards",
        "sender_email": "winner@promo-example.com",
        "recipient_email": "user@example.com",
        "subject": "Congratulations! You Have Won a Free Gift",
        "body": (
            "You have been selected to receive a free luxury gift card. "
            "Claim your prize now by clicking the link below. This "
            "limited offer expires today. No purchase necessary!"
        ),
    },

    "Verifikasi akun": {
        "sender_name": "Account Security",
        "sender_email": "security-alert@unknown-example.com",
        "recipient_email": "user@example.com",
        "subject": "Urgent: Verify Your Account Immediately",
        "body": (
            "Your account will be suspended within 24 hours. Click here "
            "immediately and enter your username and password to verify "
            "your account and avoid permanent closure."
        ),
    },

    "Penawaran kerja dari rumah": {
        "sender_name": "Online Income Team",
        "sender_email": "income@offers-example.com",
        "recipient_email": "user@example.com",
        "subject": "Make $5,000 Every Week From Home",
        "body": (
            "Earn thousands of dollars weekly with no experience. Send "
            "your bank details today to activate your guaranteed income "
            "opportunity. Limited spots available!"
        ),
    },

    "Diskon eksklusif": {
        "sender_name": "Mega Deals",
        "sender_email": "deals@shopping-example.com",
        "recipient_email": "user@example.com",
        "subject": "Exclusive Discount Just for You",
        "body": (
            "Buy now and get 90 percent off all products. Act fast, "
            "this amazing offer is available for a very limited time only. "
            "Click the link to claim your discount."
        ),
    },
}


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Email Detection",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    @import url(
        'https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap'
    );

    :root {
        --blue: #2563eb;
        --blue-dark: #1747b8;
        --blue-soft: #eef4ff;
        --text: #1f2937;
        --muted: #718096;
        --line: #e5e9f0;
        --bg: #f6f8fb;
        --white: #ffffff;
        --green: #168453;
        --red: #c43845;
    }

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    .stApp {
        background: var(--bg);
        color: var(--text);
    }

    header[data-testid="stHeader"] {
        background: rgba(246,248,251,.92);
    }

    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid var(--line);
    }

    [data-testid="stSidebar"] > div {
        padding-top: 1.15rem;
    }

    .block-container {
        max-width: 1450px;
        padding-top: 1.35rem;
        padding-bottom: 3rem;
    }

    /* BRAND */

    .brand {
        display: flex;
        align-items: center;
        gap: .75rem;
        padding: .2rem .15rem 1.35rem;
    }

    .brand-icon {
        width: 44px;
        height: 44px;
        border-radius: 13px;
        background: #2563eb;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.25rem;
        box-shadow: 0 8px 18px rgba(37,99,235,.2);
    }

    .brand-name {
        font-size: 1.28rem;
        font-weight: 800;
        letter-spacing: -.05em;
        color: #17243b;
        line-height: 1;
    }

    .brand-sub {
        margin-top: .28rem;
        color: #8995a8;
        font-size: .62rem;
        font-weight: 700;
        letter-spacing: .12em;
        text-transform: uppercase;
    }

    .nav-label {
        color: #9aa5b5;
        font-size: .64rem;
        font-weight: 800;
        letter-spacing: .12em;
        text-transform: uppercase;
        margin: .35rem 0 .15rem;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] {
        gap: .28rem;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] label {
        border-radius: 10px;
        padding: .55rem .65rem;
        border: 1px solid transparent;
    }

    [data-testid="stSidebar"]
    div[role="radiogroup"]
    label:has(input:checked) {
        background: var(--blue-soft);
        border-color: #dbe7ff;
    }

    [data-testid="stSidebar"]
    div[role="radiogroup"]
    label p {
        font-weight: 600;
        color: #526176;
    }

    [data-testid="stSidebar"]
    div[role="radiogroup"]
    label:has(input:checked) p {
        color: #2457d6;
    }

    /* TOPBAR */

    .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        border-bottom: 1px solid var(--line);
        padding-bottom: 1.1rem;
        margin-bottom: 1.45rem;
    }

    .topbar-title {
        font-weight: 800;
        font-size: 1rem;
        color: #1d2b42;
    }

    .topbar-sub {
        color: #8591a3;
        font-size: .72rem;
        margin-top: .2rem;
    }

    .active-badge {
        display: inline-flex;
        align-items: center;
        gap: .35rem;
        border: 1px solid #d8eadf;
        background: #f0faf4;
        color: #17734a;
        border-radius: 999px;
        padding: .36rem .65rem;
        font-size: .64rem;
        font-weight: 800;
    }

    /* PAGE */

    .eyebrow {
        color: #4c70bd;
        font-size: .64rem;
        font-weight: 800;
        letter-spacing: .12em;
        text-transform: uppercase;
        margin-bottom: .45rem;
    }

    .page-title {
        font-size: 1.75rem;
        font-weight: 800;
        color: #17243b;
        letter-spacing: -.055em;
        line-height: 1.1;
    }

    .page-subtitle {
        color: #718096;
        font-size: .84rem;
        line-height: 1.55;
        margin-top: .45rem;
        max-width: 760px;
    }

    /* CARDS */

    .card {
        background: white;
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 1rem 1.1rem;
        box-shadow: 0 4px 16px rgba(23,36,59,.025);
    }

    .card-title {
        color: #24334b;
        font-size: .95rem;
        font-weight: 800;
    }

    .card-subtitle {
        color: #7c899d;
        font-size: .73rem;
        line-height: 1.5;
        margin-top: .25rem;
    }

    /* HERO */

    .hero {
        background: linear-gradient(
            115deg,
            #214cae 0%,
            #2563eb 58%,
            #3b7be8 100%
        );
        border-radius: 18px;
        padding: 1.4rem 1.5rem;
        color: white;
        margin: .35rem 0 1.05rem;
        box-shadow: 0 12px 28px rgba(37,99,235,.16);
    }

    .hero-small {
        color: #d4e2ff;
        font-size: .64rem;
        font-weight: 800;
        letter-spacing: .12em;
        text-transform: uppercase;
    }

    .hero-title {
        color: white;
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: -.04em;
        margin: .35rem 0 .25rem;
    }

    .hero-text {
        color: #e5edff;
        font-size: .8rem;
        line-height: 1.55;
        max-width: 700px;
    }

    /* EMAIL LIST */

    .mail-row {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 13px;
        padding: .85rem .9rem;
        margin-bottom: .55rem;
    }

    .mail-row:hover {
        border-color: #cbd8ef;
    }

    .mail-sender {
        color: #25334a;
        font-size: .78rem;
        font-weight: 800;
    }

    .mail-subject {
        color: #35435b;
        font-size: .76rem;
        font-weight: 700;
        margin-top: .18rem;
    }

    .mail-preview {
        color: #8995a7;
        font-size: .7rem;
        line-height: 1.4;
        margin-top: .15rem;
    }

    .mail-time {
        color: #9aa5b5;
        font-size: .64rem;
        white-space: nowrap;
    }

    /* STATUS */

    .status-ok {
        border: 1px solid #cde8d8;
        background: #f0faf4;
        color: #176c48;
        padding: .9rem 1rem;
        border-radius: 13px;
    }

    .status-spam {
        border: 1px solid #f1cbd0;
        background: #fff3f4;
        color: #a42f3a;
        padding: .9rem 1rem;
        border-radius: 13px;
    }

    .status-title {
        font-size: 1.05rem;
        font-weight: 800;
        margin-top: .25rem;
    }

    .status-small {
        font-size: .72rem;
        margin-top: .35rem;
    }

    .pill {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: .23rem .58rem;
        font-size: .62rem;
        font-weight: 800;
    }

    .pill-ham {
        background: #eaf8f0;
        color: #176c48;
    }

    .pill-spam {
        background: #fff0f1;
        color: #a42f3a;
    }

    /* METRICS */

    .metric-card {
        background: white;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: .9rem 1rem;
    }

    .metric-label {
        color: #8995a8;
        font-size: .63rem;
        font-weight: 800;
        letter-spacing: .08em;
        text-transform: uppercase;
    }

    .metric-value {
        color: #17243b;
        font-size: 1.65rem;
        font-weight: 800;
        letter-spacing: -.055em;
        margin-top: .18rem;
    }

    .metric-help {
        color: #8793a5;
        font-size: .66rem;
        margin-top: .1rem;
    }

    /* RESULT */

    .result-box {
        border: 1px solid #e3e8f0;
        background: #ffffff;
        border-radius: 15px;
        padding: 1rem;
    }

    .result-title {
        color: #24334b;
        font-size: .68rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: .1em;
    }

    .result-main {
        font-size: 1.12rem;
        font-weight: 800;
        margin: .3rem 0 .75rem;
    }

    .probability-box {
        border: 1px solid #e8edf3;
        background: #f9fafc;
        border-radius: 10px;
        padding: .55rem .7rem;
    }

    .prob-label {
        color: #8a96a8;
        font-size: .61rem;
        font-weight: 800;
        text-transform: uppercase;
    }

    .prob-value {
        color: #26364e;
        font-size: 1rem;
        font-weight: 800;
        margin-top: .12rem;
    }

    /* FORM */

    div[data-testid="stForm"] {
        background: white;
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 1.05rem 1.1rem;
        box-shadow: 0 4px 16px rgba(23,36,59,.025);
    }

    /* ADMIN */

    .admin-header {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:1rem;
    }

    /* REMOVE EXCESS */

    footer {
        visibility: hidden;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# MODEL
# =========================================================

@st.cache_resource(
    show_spinner="Memuat sistem pemeriksaan email..."
)
def get_model_artifacts():

    return load_artifacts(APP_DIR)


# =========================================================
# HELPER
# =========================================================

def page_heading(
    section: str,
    title: str,
    subtitle: str,
):

    st.markdown(
        f"""
        <div class="eyebrow">
            {html.escape(section)}
        </div>

        <div class="page-title">
            {html.escape(title)}
        </div>

        <div class="page-subtitle">
            {html.escape(subtitle)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_prediction(
    label: str,
    spam_probability: float,
    ham_probability: float,
):

    spam_pct = spam_probability * 100
    ham_pct = ham_probability * 100

    if label == "SPAM":

        box_class = "status-spam"
        title = "Email masuk ke Spam"
        icon = "⚠️"
        color = "#a42f3a"

    else:

        box_class = "status-ok"
        title = "Email masuk ke Kotak Masuk"
        icon = "✓"
        color = "#176c48"

    st.markdown(
        f"""
        <div class="{box_class}">

            <div style="
                font-size:.62rem;
                font-weight:800;
                letter-spacing:.1em;
                text-transform:uppercase;
                color:{color};
            ">
                HASIL PEMERIKSAAN
            </div>

            <div class="status-title"
                 style="color:{color}">
                {icon} {title}
            </div>

            <div class="status-small">
                Email telah diperiksa dan dikategorikan
                secara otomatis.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    col1, col2 = st.columns(2)

    with col1:

        st.markdown(
            f"""
            <div class="probability-box">
                <div class="prob-label">
                    Perkiraan SPAM
                </div>

                <div class="prob-value">
                    {spam_pct:.2f}%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:

        st.markdown(
            f"""
            <div class="probability-box">
                <div class="prob-label">
                    Perkiraan HAM
                </div>

                <div class="prob-value">
                    {ham_pct:.2f}%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# =========================================================
# TULIS EMAIL
# =========================================================

def render_send_page(
    model,
    vectorizer,
):

    page_heading(
        "EMAIL BARU",
        "Tulis Email",
        "Kirim pesan ke sistem dan periksa apakah pesan tersebut "
        "termasuk email normal atau spam.",
    )

    st.markdown(
        """
        <div class="hero">

            <div class="hero-small">
                EMAIL DETECTION
            </div>

            <div class="hero-title">
                Tulis pesan seperti biasa.
            </div>

            <div class="hero-text">
                Setelah dikirim, pesan akan diperiksa secara otomatis
                sebelum masuk ke kotak surat.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(
        [1.5, .8],
        gap="large",
    )

    with left:

        sample_options = [
            "— Pilih contoh email —",
            *SAMPLES.keys(),
        ]

        selected_sample = st.selectbox(
            "Contoh email",
            sample_options,
        )

        if st.button(
            "Muat contoh",
            disabled=selected_sample == sample_options[0],
        ):

            sample = SAMPLES[
                selected_sample
            ]

            st.session_state[
                "sender_name"
            ] = sample["sender_name"]

            st.session_state[
                "sender_email"
            ] = sample["sender_email"]

            st.session_state[
                "recipient_email"
            ] = sample["recipient_email"]

            st.session_state[
                "subject"
            ] = sample["subject"]

            st.session_state[
                "body"
            ] = sample["body"]

            st.rerun()

        with st.form(
            "send_email_form"
        ):

            sender_name = st.text_input(
                "Nama pengirim",
                key="sender_name",
                placeholder="Contoh: Alex Morgan",
                max_chars=100,
            )

            sender_email = st.text_input(
                "Alamat email pengirim",
                key="sender_email",
                placeholder="nama@example.com",
                max_chars=254,
            )

            recipient_email = st.text_input(
                "Kepada",
                key="recipient_email",
                placeholder="penerima@example.com",
                max_chars=254,
            )

            subject = st.text_input(
                "Subjek",
                key="subject",
                placeholder="Masukkan subjek email",
                max_chars=MAX_SUBJECT_CHARS,
            )

            body = st.text_area(
                "Isi email",
                key="body",
                height=230,
                max_chars=MAX_BODY_CHARS,
                placeholder="Tulis pesan Anda...",
            )

            submitted = st.form_submit_button(
                "✉️  Kirim Email",
                type="primary",
                use_container_width=True,
            )

        if submitted:

            errors = []

            if not sender_name.strip():

                errors.append(
                    "Nama pengirim wajib diisi."
                )

            if not EMAIL_RE.fullmatch(
                sender_email.strip()
            ):

                errors.append(
                    "Alamat email pengirim belum valid."
                )

            if not EMAIL_RE.fullmatch(
                recipient_email.strip()
            ):

                errors.append(
                    "Alamat email tujuan belum valid."
                )

            if not subject.strip() and not body.strip():

                errors.append(
                    "Subjek atau isi email harus diisi."
                )

            now = time.time()

            submissions = [
                t
                for t in st.session_state.get(
                    "submission_times",
                    [],
                )
                if now - t < 3600
            ]

            if len(submissions) >= 20:

                errors.append(
                    "Batas pengiriman pada sesi ini telah tercapai."
                )

            if (
                submissions
                and now - submissions[-1] < 3
            ):

                errors.append(
                    "Tunggu beberapa detik sebelum mengirim email berikutnya."
                )

            if errors:

                for error in errors:
                    st.error(error)

            else:

                try:

                    result = predict_email(
                        subject,
                        body,
                        model,
                        vectorizer,
                    )

                    tracking_code = (
                        generate_tracking_code()
                    )

                    created_at = (
                        datetime.now(
                            timezone.utc
                        )
                        .isoformat(
                            timespec="seconds"
                        )
                    )

                    save_message(
                        tracking_hash=hash_tracking_code(
                            tracking_code
                        ),
                        sender_name=sender_name.strip(),
                        sender_email=sender_email.strip().lower(),
                        recipient_email=recipient_email.strip().lower(),
                        subject=(
                            subject.strip()
                            or "(Tanpa subjek)"
                        ),
                        body=body.strip(),
                        predicted_label=result.label,
                        spam_probability=result.spam_probability,
                        ham_probability=result.ham_probability,
                        created_at=created_at,
                    )

                    submissions.append(now)

                    st.session_state[
                        "submission_times"
                    ] = submissions

                    st.session_state[
                        "last_result"
                    ] = {
                        "label": result.label,
                        "spam_probability": (
                            result.spam_probability
                        ),
                        "ham_probability": (
                            result.ham_probability
                        ),
                        "tracking_code": tracking_code,
                        "subject": (
                            subject.strip()
                            or "(Tanpa subjek)"
                        ),
                    }

                    st.rerun()

                except Exception as exc:

                    st.error(
                        "Email gagal diproses atau disimpan."
                    )

                    st.caption(
                        str(exc)
                    )

    with right:

        st.markdown(
            """
            <div class="card">

                <div class="card-title">
                    Sebelum mengirim
                </div>

                <div class="card-subtitle">
                    Email yang dikirim melalui aplikasi ini
                    merupakan bagian dari sistem demonstrasi.
                </div>

                <div style="margin-top:1rem">

                    <div style="
                        display:flex;
                        gap:.65rem;
                        margin-bottom:.8rem;
                    ">

                        <div style="
                            width:28px;
                            height:28px;
                            border-radius:9px;
                            background:#eef4ff;
                            color:#2563eb;
                            display:flex;
                            align-items:center;
                            justify-content:center;
                            font-size:.72rem;
                            font-weight:800;
                        ">
                            1
                        </div>

                        <div>
                            <b style="font-size:.77rem">
                                Tulis pesan
                            </b>

                            <div style="
                                color:#7c899d;
                                font-size:.68rem;
                            ">
                                Isi pengirim, penerima,
                                subjek, dan pesan.
                            </div>
                        </div>

                    </div>


                    <div style="
                        display:flex;
                        gap:.65rem;
                        margin-bottom:.8rem;
                    ">

                        <div style="
                            width:28px;
                            height:28px;
                            border-radius:9px;
                            background:#eef4ff;
                            color:#2563eb;
                            display:flex;
                            align-items:center;
                            justify-content:center;
                            font-size:.72rem;
                            font-weight:800;
                        ">
                            2
                        </div>

                        <div>
                            <b style="font-size:.77rem">
                                Kirim
                            </b>

                            <div style="
                                color:#7c899d;
                                font-size:.68rem;
                            ">
                                Sistem memeriksa pesan
                                secara otomatis.
                            </div>
                        </div>

                    </div>


                    <div style="
                        display:flex;
                        gap:.65rem;
                    ">

                        <div style="
                            width:28px;
                            height:28px;
                            border-radius:9px;
                            background:#eef4ff;
                            color:#2563eb;
                            display:flex;
                            align-items:center;
                            justify-content:center;
                            font-size:.72rem;
                            font-weight:800;
                        ">
                            3
                        </div>

                        <div>
                            <b style="font-size:.77rem">
                                Simpan kode
                            </b>

                            <div style="
                                color:#7c899d;
                                font-size:.68rem;
                            ">
                                Gunakan kode pelacakan
                                untuk melihat hasilnya.
                            </div>
                        </div>

                    </div>

                </div>

                <hr style="
                    border:0;
                    border-top:1px solid #e8edf4;
                    margin:1.1rem 0;
                ">

                <div style="
                    color:#7c899d;
                    font-size:.66rem;
                    line-height:1.5;
                ">
                    Jangan masukkan password, OTP, nomor kartu,
                    atau informasi pribadi yang sensitif.
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

    last = st.session_state.get(
        "last_result"
    )

    if last:

        st.write("")

        st.markdown(
            """
            <div class="card-title">
                Hasil pemeriksaan
            </div>
            """,
            unsafe_allow_html=True,
        )

        render_prediction(
            last["label"],
            last["spam_probability"],
            last["ham_probability"],
        )

        st.write("")

        st.markdown(
            """
            <div class="card">

                <div style="
                    color:#7c899d;
                    font-size:.63rem;
                    font-weight:800;
                    letter-spacing:.08em;
                    text-transform:uppercase;
                ">
                    KODE PELACAKAN
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        st.code(
            last["tracking_code"],
            language=None,
        )

        st.caption(
            "Simpan kode ini. Kode digunakan untuk melihat "
            "hasil email melalui menu Lacak Pesan."
        )


# =========================================================
# LACAK PESAN
# =========================================================

def render_tracking_page():

    page_heading(
        "PELACAKAN",
        "Lacak Pesan",
        "Gunakan kode pelacakan yang Anda terima setelah "
        "mengirim email untuk melihat hasil pemeriksaannya.",
    )

    left, right = st.columns(
        [1.15, .85],
        gap="large",
    )

    with left:

        with st.form(
            "tracking_form"
        ):

            tracking_code = st.text_input(
                "Kode pelacakan",
                placeholder="Masukkan kode pelacakan Anda",
                max_chars=100,
            )

            check = st.form_submit_button(
                "🔎  Periksa Pesan",
                type="primary",
                use_container_width=True,
            )

        if check:

            if not tracking_code.strip():

                st.error(
                    "Masukkan kode pelacakan terlebih dahulu."
                )

            else:

                try:

                    message = (
                        get_message_by_tracking_hash(
                            hash_tracking_code(
                                tracking_code
                            )
                        )
                    )

                    if not message:

                        st.error(
                            "Kode pelacakan tidak ditemukan."
                        )

                    else:

                        st.success(
                            "Pesan ditemukan."
                        )

                        st.write(
                            f"**Subjek:** "
                            f"{message['subject']}"
                        )

                        st.caption(
                            f"Diterima: "
                            f"{message['created_at']}"
                        )

                        render_prediction(
                            message[
                                "predicted_label"
                            ],
                            float(
                                message[
                                    "spam_probability"
                                ]
                            ),
                            float(
                                message[
                                    "ham_probability"
                                ]
                            ),
                        )

                except Exception as exc:

                    st.error(
                        "Status pesan belum dapat diperiksa."
                    )

                    st.caption(
                        str(exc)
                    )

    with right:

        st.markdown(
            """
            <div class="card">

                <div class="card-title">
                    Tentang kode pelacakan
                </div>

                <div class="card-subtitle">
                    Kode ini diberikan setelah Anda mengirim
                    sebuah email melalui aplikasi.
                </div>

                <div style="
                    margin-top:1rem;
                    color:#2563eb;
                    font-size:1.4rem;
                ">
                    🔐
                </div>

                <div style="
                    color:#26364e;
                    font-size:.78rem;
                    font-weight:700;
                ">
                    Bersifat pribadi
                </div>

                <div style="
                    color:#7c899d;
                    font-size:.68rem;
                    line-height:1.5;
                ">
                    Gunakan kode yang sesuai dengan pesan
                    yang ingin Anda periksa.
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )


# =========================================================
# LOGIN ADMIN
# =========================================================

def render_admin_login():

    password_hash = (
        get_admin_password_hash()
    )

    if (
        not password_hash
        or password_hash
        == "PASTE_PBKDF2_HASH_FROM_GENERATOR_HERE"
    ):

        st.warning(
            "Login admin belum dikonfigurasi. "
            "Isi ADMIN_PASSWORD_HASH pada Secrets aplikasi."
        )

        return

    lock_until = float(
        st.session_state.get(
            "admin_lock_until",
            0,
        )
    )

    if time.time() < lock_until:

        st.error(
            "Terlalu banyak percobaan login. "
            "Coba lagi setelah 60 detik."
        )

        return

    st.markdown(
        """
        <div class="card">

            <div class="card-title">
                Masuk ke Panel Admin
            </div>

            <div class="card-subtitle">
                Panel ini digunakan untuk melihat
                email yang telah masuk dan hasil penyaringannya.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form(
        "admin_login"
    ):

        password = st.text_input(
            "Password admin",
            type="password",
        )

        login = st.form_submit_button(
            "Masuk",
            type="primary",
            use_container_width=True,
        )

    if login:

        if verify_admin_password(
            password,
            password_hash,
        ):

            st.session_state[
                "admin_authenticated"
            ] = True

            st.session_state[
                "admin_failed_attempts"
            ] = 0

            st.rerun()

        else:

            attempts = (
                st.session_state.get(
                    "admin_failed_attempts",
                    0,
                )
                + 1
            )

            st.session_state[
                "admin_failed_attempts"
            ] = attempts

            st.error(
                "Password admin salah."
            )

            if attempts >= 5:

                st.session_state[
                    "admin_lock_until"
                ] = time.time() + 60

                st.session_state[
                    "admin_failed_attempts"
                ] = 0


# =========================================================
# DETAIL EMAIL
# =========================================================

def render_email_detail(
    message: dict,
):

    label = message[
        "predicted_label"
    ]

    if label == "SPAM":

        pill = (
            '<span class="pill pill-spam">'
            'SPAM'
            '</span>'
        )

    else:

        pill = (
            '<span class="pill pill-ham">'
            'KOTAK MASUK'
            '</span>'
        )

    sender_name = html.escape(
        str(
            message.get(
                "sender_name",
                "",
            )
        )
    )

    sender_email = html.escape(
        str(
            message.get(
                "sender_email",
                "",
            )
        )
    )

    recipient_email = html.escape(
        str(
            message.get(
                "recipient_email",
                "",
            )
        )
    )

    subject = html.escape(
        str(
            message.get(
                "subject",
                "(Tanpa subjek)",
            )
        )
    )

    created_at = html.escape(
        str(
            message.get(
                "created_at",
                "",
            )
        )
    )

    st.markdown(
        f"""
        <div class="card">

            <div style="
                display:flex;
                justify-content:space-between;
                align-items:center;
            ">

                {pill}

                <span style="
                    color:#9aa5b5;
                    font-size:.61rem;
                    font-weight:800;
                    letter-spacing:.08em;
                ">
                    PESAN
                </span>

            </div>

            <div style="
                color:#17243b;
                font-size:1.3rem;
                font-weight:800;
                letter-spacing:-.04em;
                margin:.75rem 0;
            ">
                {subject}
            </div>

            <div style="
                color:#53627a;
                font-size:.75rem;
            ">
                <b>{sender_name}</b>
                · {sender_email}
            </div>

            <div style="
                color:#8a96a8;
                font-size:.68rem;
                margin-top:.2rem;
            ">
                Kepada: {recipient_email}
            </div>

            <div style="
                color:#9aa5b5;
                font-size:.65rem;
                margin-top:.2rem;
            ">
                {created_at}
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")

    st.markdown(
        """
        <div class="card">

            <div class="card-title">
                Isi pesan
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.text(
        str(
            message.get(
                "body",
                "",
            )
        )
    )

    st.write("")

    render_prediction(
        label,
        float(
            message[
                "spam_probability"
            ]
        ),
        float(
            message[
                "ham_probability"
            ]
        ),
    )


# =========================================================
# CSV
# =========================================================

def build_csv(
    messages: list[dict],
) -> str:

    output = io.StringIO()

    fields = [
        "id",
        "sender_name",
        "sender_email",
        "recipient_email",
        "subject",
        "body",
        "predicted_label",
        "spam_probability",
        "ham_probability",
        "created_at",
    ]

    writer = csv.DictWriter(
        output,
        fieldnames=fields,
        extrasaction="ignore",
    )

    writer.writeheader()

    writer.writerows(
        messages
    )

    return output.getvalue()


# =========================================================
# PANEL ADMIN
# =========================================================

def render_admin_page():

    page_heading(
        "PANEL ADMIN",
        "Kotak Surat",
        "Kelola email yang telah diperiksa oleh sistem.",
    )

    if not st.session_state.get(
        "admin_authenticated",
        False,
    ):

        render_admin_login()

        return

    header_left, header_right = st.columns(
        [0.8, 0.2]
    )

    with header_left:

        st.markdown(
            """
            <span class="pill pill-ham">
                ● ADMIN AKTIF
            </span>
            """,
            unsafe_allow_html=True,
        )

    with header_right:

        if st.button(
            "Keluar",
            use_container_width=True,
        ):

            st.session_state[
                "admin_authenticated"
            ] = False

            st.session_state.pop(
                "selected_message",
                None,
            )

            st.rerun()

    try:

        counts = get_counts()

        total = counts[
            "total"
        ]

        ham = counts[
            "ham"
        ]

        spam = counts[
            "spam"
        ]

        ham_pct = (
            ham / total * 100
            if total
            else 0
        )

        spam_pct = (
            spam / total * 100
            if total
            else 0
        )

        st.write("")

        c1, c2, c3 = st.columns(
            3
        )

        with c1:

            st.markdown(
                f"""
                <div class="metric-card">

                    <div class="metric-label">
                        Total Email
                    </div>

                    <div class="metric-value">
                        {total:,}
                    </div>

                    <div class="metric-help">
                        Semua pesan
                    </div>

                </div>
                """,
                unsafe_allow_html=True,
            )

        with c2:

            st.markdown(
                f"""
                <div class="metric-card">

                    <div class="metric-label">
                        Kotak Masuk
                    </div>

                    <div class="metric-value"
                         style="color:#168453">
                        {ham:,}
                    </div>

                    <div class="metric-help">
                        {ham_pct:.1f}% dari email
                    </div>

                </div>
                """,
                unsafe_allow_html=True,
            )

        with c3:

            st.markdown(
                f"""
                <div class="metric-card">

                    <div class="metric-label">
                        Spam
                    </div>

                    <div class="metric-value"
                         style="color:#c43845">
                        {spam:,}
                    </div>

                    <div class="metric-help">
                        {spam_pct:.1f}% dari email
                    </div>

                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("")

        folder = st.radio(
            "Folder",
            [
                "Kotak Masuk",
                "Spam",
                "Semua Email",
            ],
            horizontal=True,
        )

        search_col, export_col = st.columns(
            [0.76, 0.24],
            vertical_alignment="bottom",
        )

        with search_col:

            search = st.text_input(
                "Cari",
                placeholder=(
                    "Cari pengirim, subjek, atau isi pesan..."
                ),
                label_visibility="collapsed",
            )

        messages = list_messages(
            folder=folder,
            search=search,
            limit=500,
        )

        with export_col:

            if messages:

                st.download_button(
                    "Unduh CSV",
                    data=build_csv(
                        messages
                    ).encode(
                        "utf-8-sig"
                    ),
                    file_name=(
                        "email_detection_"
                        f"{folder.lower().replace(' ', '_')}"
                        ".csv"
                    ),
                    mime="text/csv",
                    use_container_width=True,
                )

        st.caption(
            f"{len(messages):,} email ditemukan"
        )

        if not messages:

            st.info(
                "Belum ada email pada folder ini."
            )

            return

        st.write("")

        list_col, detail_col = st.columns(
            [1, 1.25],
            gap="large",
        )

        ids = [
            message["id"]
            for message in messages
        ]

        current = st.session_state.get(
            "selected_message"
        )

        if current in ids:

            selected_index = (
                ids.index(
                    current
                )
            )

        else:

            selected_index = 0

        with list_col:

            st.markdown(
                """
                <div class="card-title">
                    Daftar Email
                </div>
                """,
                unsafe_allow_html=True,
            )

            selected_id = st.radio(
                "Email",
                ids,
                index=selected_index,

                format_func=lambda mid: next(
                    (
                        f"{'⚠️' if m['predicted_label'] == 'SPAM' else '✉️'}  "
                        f"{str(m.get('sender_name') or m.get('sender_email'))[:25]} · "
                        f"{str(m.get('subject') or '(Tanpa subjek)')[:42]}"
                        for m in messages
                        if m["id"] == mid
                    ),
                    str(mid),
                ),

                label_visibility="collapsed",
            )

            st.session_state[
                "selected_message"
            ] = selected_id

        with detail_col:

            message = get_message(
                selected_id
            )

            if message:

                render_email_detail(
                    message
                )

                st.write("")

                confirm = st.checkbox(
                    "Saya yakin ingin menghapus email ini",
                    key=f"confirm_{selected_id}",
                )

                if st.button(
                    "Hapus Email",
                    key=f"delete_{selected_id}",
                ):

                    if confirm:

                        delete_message(
                            selected_id
                        )

                        st.session_state.pop(
                            "selected_message",
                            None,
                        )

                        st.success(
                            "Email berhasil dihapus."
                        )

                        st.rerun()

                    else:

                        st.warning(
                            "Centang konfirmasi terlebih dahulu."
                        )

        st.write("")

        with st.expander(
            "Informasi teknis sistem"
        ):

            st.markdown(
                """
                **Algoritma:** Logistic Regression  
                **Ekstraksi fitur:** TF-IDF  
                **Konfigurasi model:** C = 10  
                **Jumlah fitur:** 5.000  
                **Penyimpanan:** Supabase  
                **Fungsi:** klasifikasi email HAM/SPAM
                """
            )

            st.caption(
                "Informasi teknis ini ditampilkan di area admin "
                "agar tidak mengganggu pengalaman pengguna biasa."
            )

    except Exception as exc:

        st.error(
            "Panel admin gagal membaca data."
        )

        st.caption(
            str(exc)
        )


# =========================================================
# INISIALISASI
# =========================================================

try:

    init_db()

    model, vectorizer = (
        get_model_artifacts()
    )

except Exception as exc:

    st.error(
        "Aplikasi belum dapat dijalankan. "
        "Periksa konfigurasi model dan database."
    )

    st.caption(
        str(exc)
    )

    st.stop()


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        """
        <div class="brand">

            <div class="brand-icon">
                ✉
            </div>

            <div>

                <div class="brand-name">
                    Email Detection
                </div>

                <div class="brand-sub">
                    Kelompok 6
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="nav-label">
            Menu
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = st.radio(
        "Navigasi",
        [
            "Tulis Email",
            "Lacak Pesan",
            "Panel Admin",
        ],

        format_func=lambda value: {
            "Tulis Email":
                "✏️  Tulis Email",

            "Lacak Pesan":
                "🔎  Lacak Pesan",

            "Panel Admin":
                "⚙️  Panel Admin",
        }[value],

        label_visibility="collapsed",
    )

    st.divider()

    st.markdown(
        """
        <div class="nav-label">
            Tentang Aplikasi
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "Email Detection merupakan aplikasi "
        "pemeriksaan email berbasis machine learning "
        "yang dikembangkan untuk proyek Kelompok 6."
    )

    st.divider()

    st.caption(
        "Jangan masukkan password, OTP, data kartu, "
        "atau informasi sensitif."
    )


# =========================================================
# TOP BAR
# =========================================================

st.markdown(
    """
    <div class="topbar">

        <div>

            <div class="topbar-title">
                Email Detection
            </div>

            <div class="topbar-sub">
                Pemeriksaan email dan penyaringan spam
            </div>

        </div>

        <div class="active-badge">
            ● SISTEM AKTIF
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# ROUTING
# =========================================================

if page == "Tulis Email":

    render_send_page(
        model,
        vectorizer,
    )

elif page == "Lacak Pesan":

    render_tracking_page()

else:

    render_admin_page() 


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Email Detection · Proyek Aplikasi Pembelajaran Mesin · "
    "Kelompok 6 · Logistic Regression"
)