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
    page_title="MailGuard — Email Security Workspace",
    page_icon="📨",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
      :root {
        --mg-ink: #17243b; --mg-muted: #718096; --mg-line: #e7ecf3;
        --mg-blue: #2457d6; --mg-blue-soft: #edf3ff; --mg-bg: #f5f7fb;
        --mg-green: #168453; --mg-red: #c43845;
      }
      html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
      .stApp { background: var(--mg-bg); color: var(--mg-ink); }
      header[data-testid="stHeader"] { background: rgba(245,247,251,.88); }
      [data-testid="stSidebar"] { background: #fff; border-right: 1px solid var(--mg-line); }
      [data-testid="stSidebar"] > div { padding-top: 1.25rem; }
      [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .65rem; }
      .block-container { max-width: 1450px; padding-top: 1.5rem; padding-bottom: 3rem; }
      .brand-wrap { display:flex; align-items:center; gap:.78rem; padding:.35rem .2rem 1.25rem; }
      .brand-icon { width:46px; height:46px; flex:0 0 46px; border-radius:15px; display:flex; align-items:center; justify-content:center;
        color:#fff; font-size:1.38rem; background:linear-gradient(145deg,#3268e7,#1743ad); box-shadow:0 8px 18px rgba(36,87,214,.2); }
      .brand-title { color:var(--mg-ink); font-size:1.32rem; font-weight:800; letter-spacing:-.055em; line-height:1.05; }
      .brand-sub { color:#8390a4; text-transform:uppercase; letter-spacing:.13em; font-size:.62rem; font-weight:800; margin-top:.3rem; }
      .sidebar-label { color:#9aa5b5; font-size:.65rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; margin:.4rem 0 .1rem; }
      [data-testid="stSidebar"] div[role="radiogroup"] { gap:.35rem; }
      [data-testid="stSidebar"] div[role="radiogroup"] label { padding:.58rem .7rem; border-radius:11px; border:1px solid transparent; background:transparent; }
      [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background:var(--mg-blue-soft); border-color:#dce7ff; }
      [data-testid="stSidebar"] div[role="radiogroup"] label p { font-weight:650; color:#42516a; }
      [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p { color:#214db6; }
      .topbar { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.1rem 0 1.25rem; border-bottom:1px solid var(--mg-line); margin-bottom:1.5rem; }
      .topbar-title { color:var(--mg-ink); font-size:1.05rem; font-weight:800; letter-spacing:-.025em; }
      .topbar-sub { color:var(--mg-muted); font-size:.75rem; margin-top:.2rem; }
      .topbar-badge { display:inline-flex; align-items:center; gap:.4rem; padding:.42rem .7rem; border-radius:999px; color:#176c48; background:#eaf8f0; border:1px solid #ccebd9; font-size:.69rem; font-weight:800; letter-spacing:.04em; white-space:nowrap; }
      .eyebrow { color:#4770c6; text-transform:uppercase; letter-spacing:.13em; font-size:.68rem; font-weight:800; margin-bottom:.5rem; }
      .page-title { color:var(--mg-ink); font-size:1.8rem; line-height:1.13; font-weight:800; letter-spacing:-.055em; margin:0; }
      .page-subtitle { color:var(--mg-muted); font-size:.92rem; margin-top:.45rem; line-height:1.55; }
      .hero { background:linear-gradient(120deg,#163c9b 0%,#2457d6 58%,#3176e8 100%); border-radius:20px; padding:1.45rem 1.55rem; color:white; box-shadow:0 14px 30px rgba(31,75,174,.16); margin:.35rem 0 1.1rem; }
      .hero-kicker { color:#c9dbff; font-size:.68rem; font-weight:800; letter-spacing:.13em; text-transform:uppercase; }
      .hero-head { color:#fff; font-size:1.42rem; font-weight:800; letter-spacing:-.04em; margin:.38rem 0 .3rem; }
      .hero-copy { color:#e1ebff; font-size:.83rem; line-height:1.55; max-width:650px; }
      .surface { background:#fff; border:1px solid var(--mg-line); border-radius:17px; padding:1.05rem 1.15rem; box-shadow:0 5px 18px rgba(23,36,59,.035); }
      .surface-title { color:var(--mg-ink); font-size:.98rem; font-weight:800; margin-bottom:.2rem; }
      .surface-copy { color:var(--mg-muted); font-size:.78rem; line-height:1.5; }
      .notice { border:1px solid #f1dfb2; background:#fffbef; color:#825616; padding:.8rem .95rem; border-radius:12px; font-size:.78rem; line-height:1.5; }
      .privacy-note { border:1px solid #dce7f8; background:#f5f8ff; color:#455d84; padding:.8rem .95rem; border-radius:12px; font-size:.78rem; line-height:1.5; }
      .status-ok { border:1px solid #ccebd9; background:#effaf3; color:#176c48; padding:.9rem 1rem; border-radius:13px; }
      .status-spam { border:1px solid #f4cbd0; background:#fff2f3; color:#a52f3a; padding:.9rem 1rem; border-radius:13px; }
      .pill { display:inline-flex; align-items:center; border-radius:999px; padding:.25rem .62rem; font-size:.68rem; font-weight:800; letter-spacing:.035em; }
      .pill-ham { color:#176c48; background:#e9f8ef; }
      .pill-spam { color:#a52f3a; background:#fff0f1; }
      .metric-card { background:#fff; border:1px solid var(--mg-line); border-radius:15px; padding:1rem 1.05rem; box-shadow:0 4px 16px rgba(23,36,59,.025); }
      .metric-label { color:#8390a4; font-size:.69rem; font-weight:800; letter-spacing:.09em; text-transform:uppercase; }
      .metric-value { color:var(--mg-ink); font-size:1.7rem; font-weight:800; letter-spacing:-.055em; margin-top:.25rem; }
      .metric-foot { color:var(--mg-muted); font-size:.72rem; margin-top:.15rem; }
      .dist-track { height:9px; width:100%; border-radius:99px; background:#edf0f5; overflow:hidden; display:flex; margin:.7rem 0 .45rem; }
      .dist-ham { height:9px; background:#1d9a68; }
      .dist-spam { height:9px; background:#db5965; }
      .dist-legend { display:flex; justify-content:space-between; color:#69788e; font-size:.72rem; font-weight:650; }
      .result-kicker { color:#8090a7; font-size:.66rem; letter-spacing:.12em; font-weight:800; text-transform:uppercase; }
      .result-label { font-size:1.5rem; font-weight:800; letter-spacing:-.045em; margin:.2rem 0 .65rem; }
      .result-score { background:#f7f9fc; border:1px solid #e9edf4; border-radius:12px; padding:.7rem .8rem; }
      .result-score-label { color:#7d899b; font-size:.67rem; text-transform:uppercase; font-weight:800; letter-spacing:.08em; }
      .result-score-value { color:var(--mg-ink); font-size:1.15rem; font-weight:800; margin-top:.15rem; }
      div.stButton > button, div.stFormSubmitButton > button { border-radius:11px; font-weight:700; min-height:2.65rem; }
      div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] { box-shadow:0 5px 12px rgba(36,87,214,.12); }
      div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea { border-radius:10px; border-color:#e1e7f0; background:#fff; }
      div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { border-radius:10px; }
      div[data-testid="stForm"] { background:#fff; border:1px solid var(--mg-line); border-radius:17px; padding:1.05rem 1.1rem; box-shadow:0 5px 18px rgba(23,36,59,.03); }
      [data-testid="stMetric"] { background:#fff; border:1px solid var(--mg-line); border-radius:14px; padding:.85rem .95rem; }
      [data-testid="stMetricLabel"] { color:#7c8aa0; }
      [data-testid="stMetricValue"] { color:var(--mg-ink); font-weight:800; }
      [data-testid="stDataFrame"] { border:1px solid var(--mg-line); border-radius:12px; overflow:hidden; }
      footer { visibility:hidden; }
      @media (max-width: 760px) {
        .block-container { padding-top:1rem; }
        .page-title { font-size:1.48rem; }
        .hero { padding:1.15rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Memuat model Logistic Regression Kelompok 6...")
def get_model_artifacts():
    return load_artifacts(APP_DIR)


def page_heading(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="eyebrow">{html.escape(kicker)}</div>'
        f'<div class="page-title">{html.escape(title)}</div>'
        f'<div class="page-subtitle">{html.escape(subtitle)}</div>',
        unsafe_allow_html=True,
    )


def render_prediction(label: str, spam_probability: float, ham_probability: float) -> None:
    spam_pct = max(0.0, min(100.0, spam_probability * 100))
    ham_pct = max(0.0, min(100.0, ham_probability * 100))
    is_spam = label == "SPAM"
    tone = "#b83242" if is_spam else "#157347"
    icon = "⚠️" if is_spam else "✓"
    label_text = "SPAM DETECTED" if is_spam else "LIKELY HAM"
    card_class = "status-spam" if is_spam else "status-ok"
    st.markdown(
        f'<div class="{card_class}">'
        f'<div class="result-kicker">MailGuard classification</div>'
        f'<div class="result-label" style="color:{tone}">{icon} {label_text}</div>'
        f'<div style="display:flex;gap:.7rem;flex-wrap:wrap">'
        f'<div class="result-score" style="flex:1;min-width:135px">'
        f'<div class="result-score-label">Spam estimate</div><div class="result-score-value">{spam_pct:.2f}%</div></div>'
        f'<div class="result-score" style="flex:1;min-width:135px">'
        f'<div class="result-score-label">Ham estimate</div><div class="result-score-value">{ham_pct:.2f}%</div></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Skor berasal dari predict_proba Logistic Regression dan belum tentu terkalibrasi "
        "sebagai probabilitas risiko yang sesungguhnya."
    )


def render_message_detail(message: dict, allow_delete: bool = False) -> None:
    label = str(message.get("predicted_label", ""))
    subject = html.escape(str(message.get("subject") or "(No subject)"))
    sender_name = html.escape(str(message.get("sender_name") or ""))
    sender_email = html.escape(str(message.get("sender_email") or ""))
    recipient_email = html.escape(str(message.get("recipient_email") or ""))
    created_at = html.escape(str(message.get("created_at") or ""))
    pill = '<span class="pill pill-spam">SPAM</span>' if label == "SPAM" else '<span class="pill pill-ham">HAM · INBOX</span>'

    st.markdown(
        '<div class="surface">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem">{pill}'
        '<span style="color:#8a96a8;font-size:.7rem;font-weight:700">MESSAGE DETAIL</span></div>'
        f'<div style="font-size:1.35rem;font-weight:800;letter-spacing:-.04em;color:#17243b;margin:.8rem 0">{subject}</div>'
        f'<div style="color:#64748b;font-size:.82rem"><b>{sender_name}</b> · {sender_email}</div>'
        f'<div style="color:#8290a4;font-size:.75rem;margin-top:.25rem">To: {recipient_email}</div>'
        f'<div style="color:#8290a4;font-size:.7rem;margin-top:.25rem">Received: {created_at}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.write("")
    st.markdown('<div class="surface-title">Message content</div>', unsafe_allow_html=True)
    st.text(str(message.get("body", "")))
    render_prediction(
        label,
        float(message.get("spam_probability", 0.0)),
        float(message.get("ham_probability", 0.0)),
    )
    if allow_delete:
        confirm_key = f"confirm_delete_{message.get('id')}"
        st.checkbox("Saya yakin ingin menghapus email ini secara permanen", key=confirm_key)
        if st.button("Hapus email secara permanen", type="secondary", key=f"delete_{message.get('id')}"):
            if st.session_state.get(confirm_key):
                delete_message(message["id"])
                st.session_state.pop("admin_selected_message", None)
                st.success("Email telah dihapus dari database.")
                st.rerun()
            else:
                st.warning("Centang konfirmasi sebelum menghapus email.")


def render_public_send(model, vectorizer) -> None:
    page_heading(
        "PUBLIC MAIL SCREENING",
        "Compose and screen an email",
        "Tulis email seperti biasa. MailGuard akan memeriksa subjek dan isi pesan menggunakan model Logistic Regression Kelompok 6.",
    )
    st.markdown(
        '<div class="hero"><div class="hero-kicker">AI-powered email screening</div>'
        '<div class="hero-head">A safer inbox starts with one check.</div>'
        '<div class="hero-copy">Kirim pesan ke mailbox demonstrasi, dapatkan klasifikasi HAM atau SPAM, '
        'dan simpan kode pelacakan pribadi untuk memeriksa hasilnya kembali.</div></div>',
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([1.55, 0.85], gap="large")
    with left_col:
        st.markdown('<div class="surface-title">New message</div>', unsafe_allow_html=True)
        st.markdown('<div class="surface-copy">Lengkapi detail pengirim, penerima, subjek, dan isi email.</div>', unsafe_allow_html=True)
        sample_options = ["— Pilih contoh email (opsional) —", *SAMPLES.keys()]
        chosen_sample = st.selectbox("Demo template", sample_options, key="sample_choice")
        if st.button("Muat contoh email", disabled=chosen_sample == sample_options[0], use_container_width=False):
            sample = SAMPLES[chosen_sample]
            st.session_state["sender_name"] = sample["sender_name"]
            st.session_state["sender_email"] = sample["sender_email"]
            st.session_state["recipient_email"] = sample["recipient_email"]
            st.session_state["subject"] = sample["subject"]
            st.session_state["body"] = sample["body"]
            st.rerun()

        with st.form("public_email_form", clear_on_submit=False):
            sender_name = st.text_input(
                "Nama pengirim", key="sender_name", max_chars=100,
                placeholder="Contoh: Alex Morgan",
            )
            sender_email = st.text_input(
                "Alamat email pengirim", key="sender_email", max_chars=254,
                placeholder="nama@example.com",
            )
            recipient_email = st.text_input(
                "Alamat email tujuan (simulasi)", key="recipient_email", max_chars=254,
                placeholder="penerima@example.edu",
            )
            subject = st.text_input(
                "Subject", key="subject", max_chars=MAX_SUBJECT_CHARS,
                placeholder="Enter an informative subject",
            )
            body = st.text_area(
                "Message", key="body", height=220, max_chars=MAX_BODY_CHARS,
                placeholder="Write the email content you want MailGuard to screen...",
            )
            submitted = st.form_submit_button(
                "✉  Send to MailGuard & detect", type="primary", use_container_width=True
            )

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

    with right_col:
        st.markdown(
            '<div class="surface"><div class="surface-title">How MailGuard works</div>'
            '<div class="surface-copy">Setiap email melewati alur klasifikasi yang sama dengan eksperimen Kelompok 6.</div>'
            '<div style="margin-top:1rem;display:flex;gap:.7rem;align-items:flex-start">'
            '<div style="background:#edf3ff;color:#2457d6;border-radius:10px;padding:.55rem">①</div>'
            '<div><b style="font-size:.83rem;color:#25334a">Text processing</b><div style="color:#718096;font-size:.73rem">Subjek dan isi digabung, lalu dinormalisasi.</div></div></div>'
            '<div style="margin-top:.9rem;display:flex;gap:.7rem;align-items:flex-start">'
            '<div style="background:#edf3ff;color:#2457d6;border-radius:10px;padding:.55rem">②</div>'
            '<div><b style="font-size:.83rem;color:#25334a">TF-IDF vectorization</b><div style="color:#718096;font-size:.73rem">Teks diubah menjadi representasi numerik.</div></div></div>'
            '<div style="margin-top:.9rem;display:flex;gap:.7rem;align-items:flex-start">'
            '<div style="background:#edf3ff;color:#2457d6;border-radius:10px;padding:.55rem">③</div>'
            '<div><b style="font-size:.83rem;color:#25334a">Logistic Regression</b><div style="color:#718096;font-size:.73rem">Model menentukan label HAM atau SPAM.</div></div></div>'
            '<div style="margin-top:.9rem;display:flex;gap:.7rem;align-items:flex-start">'
            '<div style="background:#edf3ff;color:#2457d6;border-radius:10px;padding:.55rem">④</div>'
            '<div><b style="font-size:.83rem;color:#25334a">Secure tracking</b><div style="color:#718096;font-size:.73rem">Hasil disimpan dan kode pelacakan dibuat.</div></div></div>'
            '<hr style="border:0;border-top:1px solid #e8edf4;margin:1.1rem 0">'
            '<div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:.73rem;color:#718096">MODEL</span><b style="font-size:.77rem;color:#273750">Logistic Regression</b></div>'
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-top:.45rem"><span style="font-size:.73rem;color:#718096">CONFIGURATION</span><b style="font-size:.77rem;color:#273750">C = 10 · TF-IDF</b></div>'
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-top:.45rem"><span style="font-size:.73rem;color:#718096">LANGUAGE</span><b style="font-size:.77rem;color:#273750">English</b></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.write("")
        st.markdown(
            '<div class="notice"><b>Demo environment.</b> Email disimpan untuk pemeriksaan di MailGuard, '
            'tidak diteruskan ke Gmail/Outlook. Jangan masukkan password, OTP, data keuangan, atau informasi sensitif.</div>',
            unsafe_allow_html=True,
        )

    last = st.session_state.get("last_submission_result")
    if last:
        st.write("")
        st.markdown('<div class="surface-title">Latest screening result</div>', unsafe_allow_html=True)
        if last["label"] == "SPAM":
            st.error("Email terdeteksi SPAM dan masuk ke folder Spam admin.")
        else:
            st.success("Email terdeteksi HAM dan masuk ke Inbox admin.")
        st.write(f"**Subject:** {last['subject']}")
        render_prediction(last["label"], last["spam_probability"], last["ham_probability"])
        st.markdown("**Your private tracking code**")
        st.code(last["tracking_code"], language=None)
        st.caption(
            "Simpan kode ini. Kode hanya ditampilkan setelah pengiriman dan diperlukan untuk melihat hasil melalui halaman Cek Status. "
            "MailGuard menyimpan hash kode, bukan kode aslinya."
        )


def render_public_status() -> None:
    page_heading(
        "PRIVATE TRACKING",
        "Track your email screening",
        "Masukkan kode pelacakan pribadi yang diberikan setelah pengiriman untuk melihat hasil deteksi email.",
    )
    left_col, right_col = st.columns([1.2, 0.8], gap="large")
    with left_col:
        with st.form("tracking_lookup_form"):
            code = st.text_input("Private tracking code", placeholder="Paste your tracking code here", max_chars=100)
            lookup = st.form_submit_button("Check screening status", type="primary", use_container_width=True)
        if lookup:
            if not code.strip():
                st.error("Masukkan kode pelacakan terlebih dahulu.")
            else:
                try:
                    message = get_message_by_tracking_hash(hash_tracking_code(code))
                    if not message:
                        st.error("Kode tidak ditemukan. Periksa kembali kode yang diberikan setelah pengiriman.")
                    else:
                        st.success("Email ditemukan. Berikut hasil deteksi untuk kode tersebut.")
                        st.markdown(f"**Subject:** {message['subject']}")
                        st.caption(f"Tanggal: {message['created_at']}")
                        render_prediction(
                            message["predicted_label"],
                            float(message["spam_probability"]),
                            float(message["ham_probability"]),
                        )
                except Exception as exc:
                    st.error("Status belum dapat diperiksa karena ada masalah koneksi database.")
                    st.caption(str(exc))
    with right_col:
        st.markdown(
            '<div class="surface"><div class="surface-title">Your privacy matters</div>'
            '<div class="surface-copy">Kode pelacakan berfungsi sebagai kunci untuk membuka hasil satu pengiriman. '
            'Pengunjung tidak dapat menelusuri Inbox atau Spam milik pengguna lain.</div>'
            '<div style="margin-top:1rem;color:#2457d6;font-size:1.45rem">⌁</div>'
            '<b style="font-size:.82rem;color:#26364e">Private lookup</b>'
            '<div style="font-size:.73rem;color:#718096">Hanya hasil yang cocok dengan hash kode pelacakan yang ditampilkan.</div>'
            '</div>',
            unsafe_allow_html=True,
        )


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


def _render_admin_login() -> None:
    st.markdown(
        '<div class="hero"><div class="hero-kicker">Restricted workspace</div>'
        '<div class="hero-head">Welcome back, administrator.</div>'
        '<div class="hero-copy">Masuk untuk mengelola mailbox demonstrasi, memeriksa klasifikasi, dan memantau aktivitas MailGuard.</div></div>',
        unsafe_allow_html=True,
    )
    password_hash = get_admin_password_hash()
    if not password_hash or password_hash == "PASTE_PBKDF2_HASH_FROM_GENERATOR_HERE":
        st.warning(
            "Login admin belum dikonfigurasi. Buat hash password dengan `python generate_admin_hash.py`, "
            "lalu isi ADMIN_PASSWORD_HASH pada secrets aplikasi."
        )
        return

    lock_until = float(st.session_state.get("admin_lock_until", 0))
    if time.time() < lock_until:
        st.error("Terlalu banyak percobaan login. Coba lagi setelah 60 detik.")
        return

    with st.container(border=True):
        st.markdown('<div class="surface-title">Administrator sign in</div>', unsafe_allow_html=True)
        st.caption("Akses mailbox hanya tersedia untuk admin yang terautentikasi.")
        with st.form("admin_login_form"):
            password = st.text_input("Admin password", type="password", max_chars=256)
            login = st.form_submit_button("Sign in to dashboard", type="primary", use_container_width=True)
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


def render_admin(model, vectorizer) -> None:
    page_heading(
        "ADMIN CONTROL CENTER",
        "Mailbox overview",
        "Pantau email yang diperiksa MailGuard. Seluruh data mailbox hanya tersedia untuk admin.",
    )
    if not st.session_state.get("admin_authenticated", False):
        _render_admin_login()
        return

    top_left, top_right = st.columns([0.78, 0.22])
    with top_left:
        st.markdown('<span class="pill pill-ham">● ADMIN SESSION ACTIVE</span>', unsafe_allow_html=True)
    with top_right:
        if st.button("Logout", use_container_width=True):
            st.session_state["admin_authenticated"] = False
            st.session_state.pop("admin_selected_message", None)
            st.rerun()

    try:
        counts = get_counts()
        total = counts["total"]
        ham = counts["ham"]
        spam = counts["spam"]
        ham_pct = (ham / total * 100) if total else 0
        spam_pct = (spam / total * 100) if total else 0

        metric_cols = st.columns(3, gap="medium")
        with metric_cols[0]:
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">Total screened</div>'
                f'<div class="metric-value">{total:,}</div><div class="metric-foot">All stored messages</div></div>',
                unsafe_allow_html=True,
            )
        with metric_cols[1]:
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">Inbox · HAM</div>'
                f'<div class="metric-value" style="color:#168453">{ham:,}</div>'
                f'<div class="metric-foot">{ham_pct:.1f}% of all messages</div></div>',
                unsafe_allow_html=True,
            )
        with metric_cols[2]:
            st.markdown(
                f'<div class="metric-card"><div class="metric-label">Spam detected</div>'
                f'<div class="metric-value" style="color:#c43845">{spam:,}</div>'
                f'<div class="metric-foot">{spam_pct:.1f}% of all messages</div></div>',
                unsafe_allow_html=True,
            )

        st.write("")
        st.markdown(
            '<div class="surface"><div class="surface-title">Classification distribution</div>'
            '<div class="surface-copy">Proporsi label dari seluruh email yang tersimpan di database.</div>'
            f'<div class="dist-track"><div class="dist-ham" style="width:{ham_pct:.3f}%"></div>'
            f'<div class="dist-spam" style="width:{spam_pct:.3f}%"></div></div>'
            f'<div class="dist-legend"><span>● HAM&nbsp; {ham:,} ({ham_pct:.1f}%)</span>'
            f'<span style="color:#c43845">● SPAM&nbsp; {spam:,} ({spam_pct:.1f}%)</span></div></div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Connected storage: {get_backend_name()} · List view limited to 500 messages per folder.")

        st.write("")
        st.markdown('<div class="surface-title">Mailbox</div>', unsafe_allow_html=True)
        folder = st.radio(
            "Select folder", ["All Mail", "Inbox", "Spam"], horizontal=True,
            label_visibility="collapsed",
        )
        search_col, export_col = st.columns([0.74, 0.26], vertical_alignment="bottom")
        with search_col:
            search = st.text_input(
                "Search messages", placeholder="Search sender, recipient, subject, or message content",
                label_visibility="collapsed",
            )
        messages = list_messages(folder=folder, search=search, limit=500)
        with export_col:
            if messages:
                st.download_button(
                    "Download CSV",
                    data=_build_csv(messages).encode("utf-8-sig"),
                    file_name=f"mailguard_{folder.lower().replace(' ', '_')}.csv",
                    mime="text/csv", use_container_width=True,
                )

        st.caption(f"{len(messages):,} message(s) found")
        if messages:
            pane_list, pane_detail = st.columns([0.95, 1.25], gap="large")
            message_options = [message["id"] for message in messages]
            current = st.session_state.get("admin_selected_message")
            selected_index = message_options.index(current) if current in message_options else 0
            with pane_list:
                st.markdown('<div class="surface-title">Message list</div>', unsafe_allow_html=True)
                selected_id = st.radio(
                    "Choose a message",
                    message_options,
                    index=selected_index,
                    format_func=lambda mid: next(
                        (
                            f"{'🚨' if m['predicted_label'] == 'SPAM' else '✉️'}  "
                            f"{str(m.get('sender_name') or m.get('sender_email'))[:28]} · "
                            f"{str(m.get('subject') or '(No subject)')[:48]}"
                            for m in messages if m["id"] == mid
                        ),
                        str(mid),
                    ),
                    label_visibility="collapsed",
                )
                st.session_state["admin_selected_message"] = selected_id
            with pane_detail:
                selected_message = get_message(selected_id)
                if selected_message:
                    st.markdown('<div class="surface-title">Reading pane</div>', unsafe_allow_html=True)
                    render_message_detail(selected_message, allow_delete=True)
        else:
            st.info("Mailbox is empty for this folder. Email yang dikirim melalui halaman publik akan muncul di sini.")
    except Exception as exc:
        st.error("Dashboard gagal membaca database. Periksa konfigurasi dan skema Supabase.")
        st.caption(str(exc))


try:
    init_db()
    model, vectorizer = get_model_artifacts()
except Exception as exc:
    st.error("MailGuard belum dapat dijalankan. Periksa model dan konfigurasi database aplikasi.")
    st.caption(str(exc))
    st.stop()

with st.sidebar:
    st.markdown(
        '<div class="brand-wrap"><div class="brand-icon">✉</div><div>'
        '<div class="brand-title">MailGuard</div><div class="brand-sub">Group 06 · Email AI</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sidebar-label">Workspace</div>', unsafe_allow_html=True)
    page = st.radio(
        "Application navigation",
        ["Kirim Email", "Cek Status", "Admin"],
        format_func=lambda value: {
            "Kirim Email": "✏️  Compose email",
            "Cek Status": "🔎  Track a message",
            "Admin": "🛡️  Admin workspace",
        }[value],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown('<div class="sidebar-label">Detection engine</div>', unsafe_allow_html=True)
    st.markdown("**Logistic Regression**")
    st.caption("C = 10 · TF-IDF · 5,000 features")
    st.caption("Training corpus: Enron · English")
    st.divider()
    st.markdown(
        '<div class="privacy-note"><b>Privacy reminder</b><br>Jangan mengirim password, OTP, data keuangan, atau informasi sensitif. '
        'MailGuard adalah simulasi penyaringan email, bukan layanan pengiriman email sungguhan.</div>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div class="topbar"><div><div class="topbar-title">Mail Detection</div>'
    '<div class="topbar-sub">Email screening workspace · Automatic spam detection</div></div>'
    '<div class="topbar-badge">● MODEL READY&nbsp; · &nbsp;GROUP 06</div></div>',
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
    "MailGuard · Machine Learning Application Project · Kelompok 6 · "
    "Logistic Regression (C=10). Prediksi merupakan bantuan penyaringan, bukan jaminan bahwa email aman."
)
