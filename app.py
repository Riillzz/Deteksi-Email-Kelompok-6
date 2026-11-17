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
    get_backend_name,
    get_counts,
    get_message,
    get_message_by_tracking_hash,
    init_db,
    list_messages,
    save_message,
)
from predictor import load_artifacts, predict_email
from security import generate_tracking_code, hash_tracking_code, verify_admin_password

APP_DIR = Path(__file__).resolve().parent
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_BODY_CHARS = 30000
MAX_SUBJECT_CHARS = 250

SAMPLES = {
    "HAM · Project Meeting Agenda": {
        "sender_name": "Alex Morgan",
        "sender_email": "alex.morgan@example.com",
        "recipient_email": "team@example.edu",
        "subject": "Project Meeting Agenda for Friday",
        "body": (
            "Dear team, please review the attached agenda before our project meeting "
            "on Friday at 10 AM. We will discuss the progress report and assign tasks "
            "for next week. Regards, Alex."
        ),
    },
    "HAM · Updated Course Schedule": {
        "sender_name": "Academic Office",
        "sender_email": "academic.office@example.edu",
        "recipient_email": "students@example.edu",
        "subject": "Updated Course Schedule",
        "body": (
            "Dear students, the updated lecture schedule for next week is now available. "
            "Please check the department website for room changes and contact the "
            "administration office if you have questions."
        ),
    },
    "HAM · Quarterly Report": {
        "sender_name": "Michael Brown",
        "sender_email": "michael.brown@example.com",
        "recipient_email": "john@example.com",
        "subject": "Quarterly Report Review",
        "body": (
            "Hi John, could you review the attached quarterly report before Thursday? "
            "Please add your comments to the shared document. Thank you."
        ),
    },
    "HAM · Research Seminar": {
        "sender_name": "Research Office",
        "sender_email": "research.office@example.edu",
        "recipient_email": "faculty@example.edu",
        "subject": "Invitation to Research Seminar",
        "body": (
            "Dear colleagues, you are invited to attend the research seminar on Wednesday "
            "at 2 PM in Room 204. The speaker will present the latest project findings. "
            "Please register with the department secretary."
        ),
    },
    "SPAM · Free Gift Winner": {
        "sender_name": "Lucky Rewards",
        "sender_email": "winner@promo-example.com",
        "recipient_email": "user@example.com",
        "subject": "Congratulations! You Have Won a Free Gift",
        "body": (
            "You have been selected to receive a free luxury gift card. Claim your prize "
            "now by clicking the link below. This limited offer expires today. No purchase necessary!"
        ),
    },
    "SPAM · Account Suspension": {
        "sender_name": "Account Security",
        "sender_email": "security-alert@unknown-example.com",
        "recipient_email": "user@example.com",
        "subject": "Urgent: Verify Your Account Immediately",
        "body": (
            "Your account will be suspended within 24 hours. Click here immediately and "
            "enter your username and password to verify your account and avoid permanent closure."
        ),
    },
    "SPAM · Work From Home": {
        "sender_name": "Online Income Team",
        "sender_email": "income@offers-example.com",
        "recipient_email": "user@example.com",
        "subject": "Make $5,000 Every Week From Home",
        "body": (
            "Earn thousands of dollars weekly with no experience. Send your bank details "
            "today to activate your guaranteed income opportunity. Limited spots available!"
        ),
    },
    "SPAM · Exclusive Discount": {
        "sender_name": "Mega Deals",
        "sender_email": "deals@shopping-example.com",
        "recipient_email": "user@example.com",
        "subject": "Exclusive Discount Just for You",
        "body": (
            "Buy now and get 90 percent off all products. Act fast, this amazing offer is "
            "available for a very limited time only. Click the link to claim your discount."
        ),
    },
}

st.set_page_config(
    page_title="MailGuard — Email Spam Detection",
    page_icon="📨",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
      html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
      .stApp { background: #f6f8fc; }
      [data-testid="stSidebar"] { background: #eef2f8; border-right: 1px solid #e2e8f0; }
      [data-testid="stSidebar"] > div { padding-top: 1rem; }
      .block-container { padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1380px; }
      .brand { display:flex; align-items:center; gap:.7rem; padding:.3rem .2rem 1.1rem; }
      .brand-icon { width:43px; height:43px; border-radius:14px; display:flex; align-items:center; justify-content:center;
        background:linear-gradient(140deg,#2563eb,#0f766e); color:white; font-size:1.4rem; }
      .brand-title { color:#1e2f4d; font-size:1.34rem; font-weight:800; letter-spacing:-.045em; }
      .brand-caption { color:#75839a; font-size:.67rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; }
      .hero-title { color:#172b4d; font-size:1.85rem; font-weight:800; letter-spacing:-.045em; margin:0; }
      .muted { color:#718096; font-size:.88rem; }
      .panel { background:white; border:1px solid #e5eaf2; border-radius:18px; padding:1.1rem 1.2rem; box-shadow:0 4px 18px rgba(18,38,63,.035); }
      .notice { border:1px solid #f3dfaa; background:#fffbeb; color:#854d0e; padding:.78rem .9rem; border-radius:12px; font-size:.82rem; }
      .success-note { border:1px solid #b7e4c7; background:#effaf3; color:#17663a; padding:.9rem 1rem; border-radius:13px; }
      .spam-note { border:1px solid #fecaca; background:#fff1f2; color:#a21c2b; padding:.9rem 1rem; border-radius:13px; }
      .folder-pill { display:inline-block; padding:.2rem .6rem; border-radius:999px; font-size:.72rem; font-weight:800; }
      .pill-ham { color:#17663a; background:#e7f7ed; }
      .pill-spam { color:#a21c2b; background:#ffe9eb; }
      div.stButton > button, div.stFormSubmitButton > button { border-radius:11px; font-weight:650; min-height:2.55rem; }
      div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea { border-radius:10px; }
      div[data-testid="stForm"] { background:white; border:1px solid #e5eaf2; border-radius:17px; padding:1rem 1.1rem; }
      footer { visibility:hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Memuat model Logistic Regression Kelompok 6...")
def get_model_artifacts():
    return load_artifacts(APP_DIR)


def render_prediction(label: str, spam_probability: float, ham_probability: float) -> None:
    col1, col2, col3 = st.columns(3)
    col1.metric("Prediksi", label)
    col2.metric("Estimasi SPAM", f"{spam_probability * 100:.2f}%")
    col3.metric("Estimasi HAM", f"{ham_probability * 100:.2f}%")
    if label == "SPAM":
        st.error("MailGuard mengklasifikasikan email ini sebagai SPAM.")
    else:
        st.success("MailGuard mengklasifikasikan email ini sebagai HAM.")
    st.caption(
        "Skor merupakan keluaran predict_proba Logistic Regression dan belum tentu "
        "terkalibrasi sebagai probabilitas risiko yang sesungguhnya."
    )


def render_message_detail(message: dict, allow_delete: bool = False) -> None:
    st.markdown("### Detail email")
    label = str(message.get("predicted_label", ""))
    if label == "SPAM":
        st.markdown('<span class="folder-pill pill-spam">SPAM</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="folder-pill pill-ham">HAM · INBOX</span>', unsafe_allow_html=True)
    st.markdown(f"## {message.get('subject') or '(No subject)'}")
    st.write(f"**From:** {message.get('sender_name')}  ·  {message.get('sender_email')}")
    st.write(f"**To:** {message.get('recipient_email')}")
    st.caption(f"Waktu diterima: {message.get('created_at')}")
    st.divider()
    st.markdown("**Message**")
    st.text(str(message.get("body", "")))
    st.divider()
    render_prediction(
        label,
        float(message.get("spam_probability", 0.0)),
        float(message.get("ham_probability", 0.0)),
    )
    if allow_delete:
        confirm_key = f"confirm_delete_{message.get('id')}"
        st.checkbox("Saya yakin ingin menghapus email ini secara permanen", key=confirm_key)
        if st.button("Hapus email", type="secondary", key=f"delete_{message.get('id')}"):
            if st.session_state.get(confirm_key):
                delete_message(message["id"])
                st.session_state.pop("admin_selected_message", None)
                st.success("Email telah dihapus dari database.")
                st.rerun()
            else:
                st.warning("Centang konfirmasi sebelum menghapus email.")


def render_public_send(model, vectorizer) -> None:
    st.markdown('<div class="hero-title">Kirim email untuk diperiksa</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="muted">Isi detail email. MailGuard akan memeriksa teks menggunakan model '
        'Logistic Regression Kelompok 6 lalu menyimpan hasilnya.</div>',
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown(
        '<div class="notice"><b>Catatan demonstrasi:</b> ini adalah form simulasi untuk '
        'mengirim email ke sistem deteksi. Email tidak diteruskan ke Gmail/Outlook penerima. '
        'Jangan masukkan password, OTP, atau informasi pribadi yang sensitif.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    sample_options = ["— Pilih contoh email (opsional) —", *SAMPLES.keys()]
    chosen_sample = st.selectbox("Muat contoh untuk demonstrasi", sample_options, key="sample_choice")
    if st.button("Isi form dengan contoh", disabled=chosen_sample == sample_options[0]):
        sample = SAMPLES[chosen_sample]
        st.session_state["sender_name"] = sample["sender_name"]
        st.session_state["sender_email"] = sample["sender_email"]
        st.session_state["recipient_email"] = sample["recipient_email"]
        st.session_state["subject"] = sample["subject"]
        st.session_state["body"] = sample["body"]
        st.rerun()

    with st.form("public_email_form", clear_on_submit=False):
        left, right = st.columns(2)
        with left:
            sender_name = st.text_input("Nama pengirim", key="sender_name", max_chars=100,
                                        placeholder="Contoh: Alex Morgan")
            sender_email = st.text_input("Alamat email pengirim", key="sender_email", max_chars=254,
                                          placeholder="nama@example.com")
        with right:
            recipient_email = st.text_input("Alamat email tujuan (simulasi)", key="recipient_email",
                                             max_chars=254, placeholder="penerima@example.com")
            st.caption("Alamat pengirim dan penerima hanya dicatat sebagai teks; belum diverifikasi.")
        subject = st.text_input("Subject", key="subject", max_chars=MAX_SUBJECT_CHARS,
                                placeholder="Masukkan subjek email")
        body = st.text_area("Message", key="body", height=230, max_chars=MAX_BODY_CHARS,
                            placeholder="Tulis isi email yang ingin diperiksa...")
        submitted = st.form_submit_button("📨 Kirim dan deteksi email", type="primary", use_container_width=True)

    if submitted:
        errors: list[str] = []
        if not sender_name.strip():
            errors.append("Nama pengirim wajib diisi.")
        if not EMAIL_RE.fullmatch(sender_email.strip()):
            errors.append("Alamat email pengirim belum valid.")
        if not EMAIL_RE.fullmatch(recipient_email.strip()):
            errors.append("Alamat email tujuan belum valid.")
        if not subject.strip() and not body.strip():
            errors.append("Subjek atau isi email harus diisi.")
        if len(body) > MAX_BODY_CHARS:
            errors.append(f"Isi email maksimal {MAX_BODY_CHARS:,} karakter.")

        now = time.time()
        recent_submissions = [t for t in st.session_state.get("submission_times", []) if now - t < 3600]
        if len(recent_submissions) >= 20:
            errors.append("Batas demonstrasi tercapai: maksimal 20 pengiriman per sesi setiap jam.")
        if recent_submissions and now - recent_submissions[-1] < 3:
            errors.append("Tunggu beberapa detik sebelum mengirim email berikutnya.")

        if errors:
            for error in errors:
                st.error(error)
        else:
            try:
                result = predict_email(subject, body, model, vectorizer)
                tracking_code = generate_tracking_code()
                created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                save_message(
                    tracking_hash=hash_tracking_code(tracking_code),
                    sender_name=sender_name.strip(),
                    sender_email=sender_email.strip().lower(),
                    recipient_email=recipient_email.strip().lower(),
                    subject=subject.strip() or "(No subject)",
                    body=body.strip(),
                    predicted_label=result.label,
                    spam_probability=result.spam_probability,
                    ham_probability=result.ham_probability,
                    created_at=created_at,
                )
                recent_submissions.append(now)
                st.session_state["submission_times"] = recent_submissions
                st.session_state["last_submission_result"] = {
                    "tracking_code": tracking_code,
                    "label": result.label,
                    "spam_probability": result.spam_probability,
                    "ham_probability": result.ham_probability,
                    "subject": subject.strip() or "(No subject)",
                }
                st.rerun()
            except Exception as exc:
                st.error("Email gagal diproses atau disimpan. Periksa konfigurasi database aplikasi.")
                st.caption(str(exc))

    last = st.session_state.get("last_submission_result")
    if last:
        st.divider()
        st.markdown("### Hasil pemeriksaan email terakhir")
        if last["label"] == "SPAM":
            st.error("🚨 Email terdeteksi SPAM dan masuk ke folder Spam admin.")
        else:
            st.success("✅ Email terdeteksi HAM dan masuk ke Inbox admin.")
        st.write(f"**Subject:** {last['subject']}")
        render_prediction(last["label"], last["spam_probability"], last["ham_probability"])
        st.markdown("#### Kode pelacakan pribadi")
        st.code(last["tracking_code"], language=None)
        st.warning(
            "Simpan kode ini. Kode hanya ditampilkan setelah pengiriman dan diperlukan untuk "
            "melihat hasil kiriman melalui halaman Cek Status. MailGuard menyimpan hash kode, bukan kode aslinya."
        )


def render_public_status() -> None:
    st.markdown('<div class="hero-title">Cek status email</div>', unsafe_allow_html=True)
    st.markdown('<div class="muted">Masukkan kode pelacakan yang diberikan setelah email dikirim.</div>',
                unsafe_allow_html=True)
    with st.form("tracking_lookup_form"):
        code = st.text_input("Kode pelacakan", placeholder="Tempel kode pelacakan di sini", max_chars=100)
        lookup = st.form_submit_button("Periksa status", type="primary")
    if lookup:
        if not code.strip():
            st.error("Masukkan kode pelacakan terlebih dahulu.")
        else:
            try:
                message = get_message_by_tracking_hash(hash_tracking_code(code))
                if not message:
                    st.error("Kode tidak ditemukan. Periksa kembali kode yang diberikan setelah pengiriman.")
                else:
                    st.success("Email ditemukan. Ini adalah hasil deteksi untuk kode tersebut.")
                    st.write(f"**Subject:** {message['subject']}")
                    st.write(f"**Tanggal:** {message['created_at']}")
                    render_prediction(
                        message["predicted_label"],
                        float(message["spam_probability"]),
                        float(message["ham_probability"]),
                    )
            except Exception as exc:
                st.error("Status belum dapat diperiksa karena ada masalah koneksi database.")
                st.caption(str(exc))


def _build_csv(messages: list[dict]) -> str:
    output = io.StringIO()
    fields = [
        "id", "sender_name", "sender_email", "recipient_email", "subject", "body",
        "predicted_label", "spam_probability", "ham_probability", "created_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(messages)
    return output.getvalue()


def render_admin(model, vectorizer) -> None:
    st.markdown('<div class="hero-title">Admin dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="muted">Area privat untuk memantau email yang diperiksa MailGuard.</div>',
                unsafe_allow_html=True)
    if not st.session_state.get("admin_authenticated", False):
        password_hash = get_admin_password_hash()
        if not password_hash or password_hash == "PASTE_PBKDF2_HASH_FROM_GENERATOR_HERE":
            st.warning(
                "Login admin belum dikonfigurasi. Buat hash password dengan "
                "`python generate_admin_hash.py`, lalu isi ADMIN_PASSWORD_HASH pada secrets aplikasi."
            )
            return

        lock_until = float(st.session_state.get("admin_lock_until", 0))
        if time.time() < lock_until:
            st.error("Terlalu banyak percobaan login. Coba lagi setelah 60 detik.")
            return

        with st.form("admin_login_form"):
            password = st.text_input("Password admin", type="password", max_chars=256)
            login = st.form_submit_button("Login admin", type="primary", use_container_width=True)
        if login:
            if verify_admin_password(password, password_hash):
                st.session_state["admin_authenticated"] = True
                st.session_state["admin_failed_attempts"] = 0
                st.rerun()
            else:
                attempts = int(st.session_state.get("admin_failed_attempts", 0)) + 1
                st.session_state["admin_failed_attempts"] = attempts
                st.error("Password admin salah.")
                if attempts >= 5:
                    st.session_state["admin_lock_until"] = time.time() + 60
                    st.session_state["admin_failed_attempts"] = 0
        return

    top_left, top_right = st.columns([0.8, 0.2])
    with top_left:
        st.success("Login admin aktif. Data mailbox hanya ditampilkan pada area ini.")
    with top_right:
        if st.button("Logout", use_container_width=True):
            st.session_state["admin_authenticated"] = False
            st.session_state.pop("admin_selected_message", None)
            st.rerun()

    try:
        counts = get_counts()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total email", counts["total"])
        c2.metric("Inbox · HAM", counts["ham"])
        c3.metric("Spam", counts["spam"])
        st.caption(f"Database aktif: {get_backend_name()} · Data terbaru dibatasi hingga 500 email per folder.")

        folder = st.radio("Folder mailbox", ["All Mail", "Inbox", "Spam"], horizontal=True)
        search = st.text_input("Cari email", placeholder="Pengirim, penerima, subjek, atau isi email")
        messages = list_messages(folder=folder, search=search, limit=500)
        st.caption(f"Menampilkan {len(messages)} email")

        if messages:
            export_messages = list_messages(folder=folder, search=search, limit=500)
            st.download_button(
                "Download hasil sebagai CSV",
                data=_build_csv(export_messages).encode("utf-8-sig"),
                file_name=f"mailguard_{folder.lower().replace(' ', '_')}.csv",
                mime="text/csv",
            )
            options = [message["id"] for message in messages]
            selected_id = st.selectbox(
                "Pilih email untuk melihat detail",
                options,
                index=0,
                format_func=lambda mid: next(
                    (f"{m['predicted_label']} · {m['subject']} · {m['sender_email']}"
                     for m in messages if m["id"] == mid), str(mid)
                ),
            )
            selected_message = get_message(selected_id)
            if selected_message:
                render_message_detail(selected_message, allow_delete=True)
        else:
            st.info("Belum ada email pada folder ini.")
    except Exception as exc:
        st.error("Dashboard gagal membaca database. Periksa konfigurasi dan skema Supabase.")
        st.caption(str(exc))


try:
    init_db()
    model, vectorizer = get_model_artifacts()
except Exception as exc:
    st.error("MailGuard belum dapat dijalankan. Periksa model dan konfigurasi database.")
    st.caption(str(exc))
    st.stop()

with st.sidebar:
    st.markdown(
        '<div class="brand"><div class="brand-icon">✉</div><div>'
        '<div class="brand-title">MailGuard</div><div class="brand-caption">Kelompok 6 · ML Mail</div></div></div>',
        unsafe_allow_html=True,
    )
    st.caption("MAILGUARD")
    page = st.radio(
        "Navigasi aplikasi",
        ["Kirim Email", "Cek Status", "Admin"],
        format_func=lambda value: {
            "Kirim Email": "✏️  Kirim email",
            "Cek Status": "🔎  Cek status",
            "Admin": "🛡️  Admin dashboard",
        }[value],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("MESIN DETEKSI")
    st.markdown("**Logistic Regression**")
    st.caption("C = 10 · TF-IDF · 5.000 fitur")
    st.caption("Dataset pelatihan: Enron · Bahasa Inggris")
    st.divider()
    st.markdown(
        '<div class="notice">Jangan mengirim password, OTP, data keuangan, atau informasi rahasia. '
        'Form ini merupakan simulasi deteksi email dan bukan layanan pengiriman email sungguhan.</div>',
        unsafe_allow_html=True,
    )

header_left, header_right = st.columns([0.78, 0.22])
with header_left:
    st.markdown("## MailGuard Mail")
    st.caption("Email screening workspace · Automatic spam detection")
with header_right:
    st.markdown(
        '<div style="text-align:right;color:#718096;font-size:.75rem;padding-top:.65rem">'
        '<b>PUBLIC DEMO</b><br>Kelompok 6</div>',
        unsafe_allow_html=True,
    )

if page == "Kirim Email":
    render_public_send(model, vectorizer)
elif page == "Cek Status":
    render_public_status()
else:
    render_admin(model, vectorizer)

st.divider()
st.caption(
    "MailGuard · Project Aplikasi Pembelajaran Mesin · Kelompok 6 · "
    "Logistic Regression (C=10). Prediksi bersifat bantuan penyaringan, bukan jaminan email aman."
)
