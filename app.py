from __future__ import annotations

import csv
import io
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from config import get_admin_password_hash
from database import (
    delete_message,
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
# STYLE
# =========================================================

st.markdown(
    """
<style>

.stApp {
    background-color: #f7f8fa;
}

.block-container {
    max-width: 1100px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #e5e7eb;
}

[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem;
}

h1, h2, h3 {
    color: #20252b;
}

.app-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #20252b;
}

.app-subtitle {
    font-size: 0.75rem;
    color: #8a919c;
    margin-bottom: 1.5rem;
}

.small-label {
    font-size: 0.72rem;
    color: #8a919c;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
}

div[data-testid="stMetric"] {
    background-color: white;
    border: 1px solid #e4e7eb;
    border-radius: 10px;
    padding: 0.8rem;
}

div[data-testid="stMetricValue"] {
    color: #20252b;
}

div[data-testid="stForm"] {
    background-color: white;
    border: 1px solid #e4e7eb;
    border-radius: 10px;
    padding: 1.2rem;
}

.email-card {
    background-color: white;
    border: 1px solid #e4e7eb;
    border-radius: 10px;
    padding: 1rem;
}

.info-text {
    color: #747b85;
    font-size: 0.82rem;
}

.footer {
    text-align: center;
    color: #9aa0a8;
    font-size: 0.7rem;
    margin-top: 2rem;
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

def page_heading(title: str, subtitle: str):

    st.title(title)

    st.caption(subtitle)


def render_prediction(
    label: str,
    spam_probability: float,
    ham_probability: float,
):

    spam_pct = spam_probability * 100
    ham_pct = ham_probability * 100

    if label == "SPAM":

        st.error(
            "⚠️ Email terdeteksi sebagai SPAM"
        )

        st.caption(
            "Sistem menilai email ini memiliki karakteristik "
            "yang lebih dekat dengan pesan spam."
        )

    else:

        st.success(
            "✓ Email terdeteksi sebagai HAM"
        )

        st.caption(
            "Sistem menilai email ini memiliki karakteristik "
            "yang lebih dekat dengan pesan normal."
        )

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Probabilitas SPAM",
            f"{spam_pct:.2f}%",
        )

    with col2:

        st.metric(
            "Probabilitas HAM",
            f"{ham_pct:.2f}%",
        )


def build_csv(messages: list[dict]) -> str:

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

    writer.writerows(messages)

    return output.getvalue()


# =========================================================
# TULIS EMAIL
# =========================================================

def render_send_page(model, vectorizer):

    page_heading(
        "Tulis Email",
        "Kirim email untuk diperiksa oleh sistem.",
    )

    st.info(
        "Email yang dikirim akan diperiksa menggunakan "
        "model Logistic Regression untuk menentukan apakah "
        "pesan termasuk HAM atau SPAM."
    )

    st.subheader("Coba contoh email")

    st.caption(
        "Pilih contoh untuk mengisi form secara otomatis."
    )

    sample_col, button_col = st.columns(
        [3, 1],
        vertical_alignment="bottom",
    )

    with sample_col:

        sample_options = [
            "— Pilih contoh email —",
            *SAMPLES.keys(),
        ]

        selected_sample = st.selectbox(
            "Contoh email",
            sample_options,
            label_visibility="collapsed",
        )

    with button_col:

        load_sample = st.button(
            "Muat contoh",
            use_container_width=True,
            disabled=(
                selected_sample
                == sample_options[0]
            ),
        )

    if load_sample:

        sample = SAMPLES[selected_sample]

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

    st.divider()

    st.subheader("Detail email")

    with st.form("send_email_form"):

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
            height=240,
            max_chars=MAX_BODY_CHARS,
            placeholder="Tulis isi email di sini...",
        )

        submitted = st.form_submit_button(
            "✉️ Kirim Email",
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

        if (
            not subject.strip()
            and not body.strip()
        ):

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
                    ).isoformat(
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

                st.caption(str(exc))

    # =====================================================
    # HASIL TERAKHIR
    # =====================================================

    last_result = st.session_state.get(
        "last_result"
    )

    if last_result:

        st.divider()

        st.subheader(
            "Hasil email terakhir"
        )

        st.caption(
            f"Subjek: {last_result['subject']}"
        )

        render_prediction(
            last_result["label"],
            float(
                last_result[
                    "spam_probability"
                ]
            ),
            float(
                last_result[
                    "ham_probability"
                ]
            ),
        )

        st.write("")

        st.write(
            "Kode pelacakan:"
        )

        st.code(
            last_result["tracking_code"],
            language=None,
        )

        st.caption(
            "Simpan kode tersebut untuk melihat "
            "hasil email melalui menu Lacak Pesan."
        )


# =========================================================
# LACAK PESAN
# =========================================================

def render_tracking_page():

    page_heading(
        "Lacak Pesan",
        "Periksa kembali hasil email menggunakan kode pelacakan.",
    )

    left, right = st.columns(
        [1.5, 0.8],
        gap="large",
    )

    with left:

        with st.form(
            "tracking_form"
        ):

            tracking_code = st.text_input(
                "Kode pelacakan",
                placeholder="Masukkan kode pelacakan",
            )

            check = st.form_submit_button(
                "🔎 Periksa Pesan",
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

                        st.write(
                            f"**Pengirim:** "
                            f"{message['sender_name']} "
                            f"({message['sender_email']})"
                        )

                        st.caption(
                            f"Dibuat: {message['created_at']}"
                        )

                        st.divider()

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

                    st.caption(str(exc))

    with right:

        st.info(
            """
            **Tentang kode pelacakan**

            Kode pelacakan diberikan setelah email
            berhasil diproses.

            Gunakan kode tersebut untuk melihat
            kembali hasil pemeriksaan email.
            """
        )


# =========================================================
# LOGIN ADMIN
# =========================================================

def render_admin_login():

    st.subheader("Login Admin")

    st.caption(
        "Masukkan password untuk membuka panel admin."
    )

    lock_until = st.session_state.get(
        "admin_lock_until",
        0,
    )

    if time.time() < lock_until:

        remaining = int(
            lock_until - time.time()
        )

        st.warning(
            f"Terlalu banyak percobaan. "
            f"Coba lagi dalam {remaining} detik."
        )

        return

    with st.form(
        "admin_login_form"
    ):

        password = st.text_input(
            "Password",
            type="password",
        )

        login = st.form_submit_button(
            "Masuk",
            type="primary",
            use_container_width=True,
        )

    if login:

        stored_hash = (
            get_admin_password_hash()
        )

        if verify_admin_password(
            password,
            stored_hash,
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

        st.warning(
            "⚠️ Email ini dikategorikan sebagai SPAM."
        )

    else:

        st.success(
            "✓ Email ini dikategorikan sebagai HAM."
        )

    st.subheader(
        message.get(
            "subject",
            "(Tanpa subjek)",
        )
    )

    st.write(
        f"**Pengirim:** "
        f"{message.get('sender_name', '')} "
        f"({message.get('sender_email', '')})"
    )

    st.write(
        f"**Kepada:** "
        f"{message.get('recipient_email', '')}"
    )

    st.caption(
        f"Waktu: {message.get('created_at', '')}"
    )

    st.divider()

    st.write("**Isi pesan**")

    st.text(
        str(
            message.get(
                "body",
                "",
            )
        )
    )

    st.divider()

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
# PANEL ADMIN
# =========================================================

def render_admin_page():

    page_heading(
        "Panel Admin",
        "Lihat dan kelola email yang telah diperiksa.",
    )

    if not st.session_state.get(
        "admin_authenticated",
        False,
    ):

        render_admin_login()

        return

    top_left, top_right = st.columns(
        [0.8, 0.2]
    )

    with top_left:

        st.success(
            "Admin sedang masuk."
        )

    with top_right:

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

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Total Email",
                f"{total:,}",
            )

        with c2:

            st.metric(
                "Kotak Masuk",
                f"{ham:,}",
            )

        with c3:

            st.metric(
                "Spam",
                f"{spam:,}",
            )

        st.divider()

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
            [0.75, 0.25],
            vertical_alignment="bottom",
        )

        with search_col:

            search = st.text_input(
                "Cari email",
                placeholder=(
                    "Cari pengirim, subjek, atau isi pesan..."
                ),
            )

        messages = list_messages(
            folder=folder,
            search=search,
            limit=500,
        )

        with export_col:

            if messages:

                st.download_button(
                    "⬇️ Unduh CSV",
                    data=build_csv(
                        messages
                    ).encode(
                        "utf-8-sig"
                    ),
                    file_name=(
                        "email_detection_"
                        f"{folder.lower().replace(' ', '_')}.csv"
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

        st.divider()

        list_col, detail_col = st.columns(
            [0.9, 1.4],
            gap="large",
        )

        ids = [
            message["id"]
            for message in messages
        ]

        current = (
            st.session_state.get(
                "selected_message"
            )
        )

        if current in ids:

            selected_index = ids.index(
                current
            )

        else:

            selected_index = 0

        with list_col:

            st.subheader(
                "Daftar Email"
            )

            selected_id = st.radio(
                "Email",
                ids,
                index=selected_index,
                format_func=lambda mid: next(
                    (
                        f"{'⚠️' if m['predicted_label'] == 'SPAM' else '✉️'} "
                        f"{str(m.get('sender_name') or m.get('sender_email'))[:22]}"
                        f" — "
                        f"{str(m.get('subject') or '(Tanpa subjek)')[:35]}"
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

                st.divider()

                confirm = st.checkbox(
                    "Saya yakin ingin menghapus email ini",
                    key=(
                        f"confirm_{selected_id}"
                    ),
                )

                if st.button(
                    "🗑️ Hapus Email",
                    key=(
                        f"delete_{selected_id}"
                    ),
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

        st.divider()

        with st.expander(
            "Informasi teknis sistem"
        ):

            col1, col2 = st.columns(2)

            with col1:

                st.write(
                    "**Algoritma:** Logistic Regression"
                )

                st.write(
                    "**Ekstraksi fitur:** TF-IDF"
                )

                st.write(
                    "**Konfigurasi model:** C = 10"
                )

            with col2:

                st.write(
                    "**Jumlah fitur:** 5.000"
                )

                st.write(
                    "**Penyimpanan:** Supabase"
                )

                st.write(
                    "**Klasifikasi:** HAM / SPAM"
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

    st.caption(str(exc))

    st.stop()


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        '<div class="app-title">✉️ Email Detection</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="app-subtitle">'
        'Proyek Machine Learning · Kelompok 6'
        '</div>',
        unsafe_allow_html=True,
    )

    st.caption("MENU")

    page = st.radio(
        "Navigasi",
        [
            "Tulis Email",
            "Lacak Pesan",
            "Panel Admin",
        ],
        format_func=lambda value: {
            "Tulis Email": "✏️  Tulis Email",
            "Lacak Pesan": "🔎  Lacak Pesan",
            "Panel Admin": "⚙️  Panel Admin",
        }[value],
        label_visibility="collapsed",
    )

    st.divider()

    st.caption(
        "Aplikasi pemeriksaan email berbasis "
        "Machine Learning dengan Logistic Regression."
    )

    st.caption(
        "Jangan masukkan password, OTP, data kartu, "
        "atau informasi sensitif."
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

st.markdown(
    '<div class="footer">'
    'Email Detection · Kelompok 6 · Logistic Regression'
    '</div>',
    unsafe_allow_html=True,
)