# MailGuard V2 — Public Email Submission + Admin Dashboard

Prototipe sistem deteksi email spam Kelompok 6. Pengunjung dapat mengirim teks email melalui halaman web, mendapat hasil prediksi SPAM/HAM, dan menggunakan kode pelacakan untuk melihat hasil kirimannya sendiri. Admin harus login untuk melihat seluruh email, statistik, mengunduh CSV, dan menghapus data.

> **Batas sistem:** MailGuard V2 menerima email melalui form web dan menyimpannya di database. Sistem ini belum menerima email langsung dari inbox Gmail/Outlook melalui SMTP/MX dan belum meneruskan email ke alamat tujuan. Field From/To saat ini hanya data yang diketik pengguna dan tidak diverifikasi.

## 1. Fitur V2

### Halaman publik
- Kirim email melalui form: nama pengirim, alamat From, alamat To, Subject, dan Message.
- Deteksi otomatis menggunakan model Logistic Regression Kelompok 6.
- Hasil SPAM/HAM dan estimasi probabilitas ditampilkan setelah pengiriman.
- Email diberi kode pelacakan rahasia; pengguna dapat melihat hasilnya sendiri melalui halaman **Cek Status**.
- Kode pelacakan mentah hanya ditampilkan setelah pengiriman; database hanya menyimpan SHA-256 hash-nya.
- Maksimal 20 pengiriman per sesi per jam dan cooldown 3 detik. Pembatasan ini hanya pengaman demo berbasis sesi, bukan perlindungan anti-bot produksi.
- Delapan contoh email bahasa Inggris disediakan untuk demonstrasi.

### Admin dashboard
- Login admin menggunakan hash PBKDF2-SHA256.
- Melihat statistik total email, HAM, dan SPAM.
- Membuka folder All Mail, Inbox (HAM), dan Spam.
- Pencarian email dan tampilan detail.
- Mengunduh hasil folder sebagai CSV.
- Menghapus email dengan konfirmasi.

### Database
- Default: SQLite lokal di `data/mailguard_v2.db`.
- Opsional: Supabase PostgreSQL untuk penyimpanan online persisten.
- Tidak ada halaman publik yang menampilkan mailbox atau pesan milik pengunjung lain.

## 2. Menjalankan lokal di Windows

Persyaratan: Python 3.11 atau 3.12 direkomendasikan.

1. Ekstrak ZIP.
2. Klik dua kali `run_app_windows.bat`.
3. Browser akan membuka `http://localhost:8501`.
4. Tanpa konfigurasi Supabase, aplikasi otomatis memakai SQLite lokal.
5. Untuk membuka dashboard admin, buat hash password seperti langkah 3 di bawah.

Atau jalankan manual melalui PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

## 3. Mengatur password admin

1. Buka terminal di folder aplikasi.
2. Jalankan:

   ```powershell
   python generate_admin_hash.py
   ```
3. Masukkan password minimal 12 karakter dua kali. Password tidak ditampilkan di terminal.
4. Salin hasil `ADMIN_PASSWORD_HASH` ke file `.streamlit/secrets.toml`.
5. Salin template `.streamlit/secrets.toml.example` menjadi `.streamlit/secrets.toml`, lalu isi hash tersebut.
6. Restart aplikasi.

Contoh format file lokal (gunakan nilai hasil generator sendiri):

```toml
ADMIN_PASSWORD_HASH = "pbkdf2_sha256$600000$...$..."
```

Jangan commit `.streamlit/secrets.toml` ke GitHub. File ini telah dimasukkan ke `.gitignore`.

## 4. Mengaktifkan database online Supabase

Jika belum ingin membuat akun Supabase, lewati bagian ini: SQLite lokal sudah dapat digunakan untuk demonstrasi di satu komputer.

1. Buat project di Supabase.
2. Buka **SQL Editor** pada project tersebut.
3. Salin dan jalankan seluruh isi `supabase_schema.sql`. Ini membuat tabel `public.messages`, indeks, dan mengaktifkan Row Level Security.
4. Buka pengaturan API/keys project dan salin Project URL serta server-side secret key (atau service-role key yang tersedia pada project).
5. Isi `.streamlit/secrets.toml` lokal atau kolom **Secrets** pada Streamlit Community Cloud dengan:

   ```toml
   SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
   SUPABASE_SECRET_KEY = "sb_secret_YOUR_SERVER_SIDE_SECRET_KEY"
   ADMIN_PASSWORD_HASH = "HASH_DARI_GENERATOR"
   ```

6. Pastikan paket `supabase` terpasang melalui `pip install -r requirements.txt`.
7. Restart aplikasi. MailGuard akan memilih Supabase jika kedua konfigurasi database ditemukan. Kode aplikasi mendukung `SUPABASE_SECRET_KEY` terbaru, serta nama legacy `SUPABASE_SERVICE_ROLE_KEY` dan `SUPABASE_KEY`.

**Keamanan kunci:** secret/service-role key hanya boleh berada di Streamlit secrets atau environment variable server. Jangan pernah menaruhnya di kode frontend, file HTML publik, screenshot, atau repository GitHub. Tabel sengaja tidak mempunyai policy untuk role `anon`/`authenticated`; aplikasi mengaksesnya dari sisi server.

## 5. Deploy ke Streamlit Community Cloud

Sebelum deploy publik:

1. Pastikan aplikasi diuji lokal.
2. Buat repository GitHub khusus aplikasi.
3. Upload source code, folder `models/`, `requirements.txt`, `supabase_schema.sql`, dan file pendukung. Jangan upload database SQLite lokal atau file `secrets.toml` asli.
4. Buka Streamlit Community Cloud, pilih **Create app**, lalu tentukan repository, branch `main`, dan file path `app.py`.
5. Pada **Advanced settings**, biarkan Python `3.12` (default Community Cloud saat panduan ini disiapkan) dan isi kolom **Secrets** dengan TOML berisi `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, serta `ADMIN_PASSWORD_HASH`.
6. Klik **Deploy**. Setelah aplikasi aktif, uji pengiriman email, kode pelacakan, login admin, Inbox, dan Spam.
7. Setiap perubahan yang di-push ke repository GitHub akan memicu pembaruan aplikasi di Community Cloud.

Panduan resmi:
- Streamlit deployment: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- Streamlit secrets: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
- Supabase Python insert: https://supabase.com/docs/reference/python/insert

Streamlit Community Cloud mengambil source dari GitHub, menyediakan kolom Secrets saat deployment, dan mengikuti perubahan yang di-push ke repository. Jangan pernah menyimpan `secrets.toml`, secret key Supabase, atau password admin di repository. Periksa kembali log deploy jika instalasi dependensi atau koneksi database gagal.

## 6. Alur kerja aplikasi

```text
Pengunjung
   |
   v
Form Kirim Email
   |
   v
Gabungkan Subject + Message
   |
   v
TF-IDF Kelompok 6
   |
   v
Logistic Regression (C=10)
   |
   +------ HAM ------> Folder Inbox admin
   |
   +------ SPAM -----> Folder Spam admin
   |
   v
Simpan email + skor + hash kode pelacakan ke database
   |
   +------> Pengunjung menerima kode pelacakan
   |
   +------> Admin melihat semua data setelah login
```

## 7. Model machine learning

Aplikasi menggunakan artefak eksperimen Kelompok 6 yang disimpan dalam `models/`:

- Model: Logistic Regression, `C=10.0`, `solver=liblinear`, `max_iter=1000`.
- TF-IDF: unigram, `min_df=2`, `max_features=5000`, `norm=l2`, `stop_words=None`, lowercase aktif.
- Input model: gabungan Subject dan Message, kemudian normalisasi whitespace.
- Label: `0 = HAM`, `1 = SPAM`.

Probabilitas yang ditampilkan merupakan keluaran `predict_proba`; belum tentu terkalibrasi. Model dilatih pada dataset Enron berbahasa Inggris sehingga kemampuan untuk email Indonesia belum dijamin.

## 8. Keamanan, privasi, dan keterbatasan

- Pengunjung publik hanya dapat melihat hasil dengan kode pelacakan yang mereka miliki; daftar email tidak tersedia di halaman publik.
- Admin dapat melihat seluruh isi email. Gunakan password admin yang kuat dan rahasiakan kuncinya.
- Identitas From tidak diverifikasi; form dapat disalahgunakan untuk memasukkan alamat orang lain.
- Pembatasan pengiriman berbasis sesi mudah dilewati dan bukan rate-limit tingkat jaringan.
- Sebelum dipakai secara luas, tambahkan CAPTCHA/anti-bot, rate limiting di reverse proxy/API gateway, verifikasi email, kebijakan retensi dan penghapusan data, HTTPS, backup database, audit log, serta autentikasi admin yang dikelola identity provider.
- Jangan mengirim password, OTP, data keuangan, data kesehatan, atau informasi rahasia.
- Prediksi machine learning adalah bantuan penyaringan, bukan jaminan bahwa email aman atau berbahaya.
- Untuk menerima email sungguhan dari Gmail/Outlook, diperlukan penyedia inbound email, domain dengan DNS/MX record, endpoint webhook, verifikasi signature webhook, dan penanganan abuse. Hal ini terpisah dari form publik V2.

## 9. File utama

- `app.py` — UI publik, halaman status, dan dashboard admin.
- `predictor.py` — memuat model dan melakukan prediksi.
- `database.py` — adapter SQLite/Supabase.
- `security.py` — kode pelacakan dan password hash.
- `config.py` — pembacaan secrets/environment variables.
- `supabase_schema.sql` — skema database online.
- `generate_admin_hash.py` — generator password hash.
- `models/` — artefak Logistic Regression dan TF-IDF.
