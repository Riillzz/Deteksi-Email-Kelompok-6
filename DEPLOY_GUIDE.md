# Deploy MailGuard V2 ke Streamlit Community Cloud

Panduan ini untuk mempublikasikan prototipe Kelompok 6 agar dapat dibuka melalui link.

## Sebelum mulai

Siapkan:
- Akun GitHub.
- Akun Streamlit Community Cloud: https://share.streamlit.io/
- Akun Supabase: https://supabase.com/ (wajib untuk penyimpanan data online yang persisten).

**Jangan masukkan password admin, file `.streamlit/secrets.toml`, Supabase secret key, atau database SQLite ke repository GitHub.** `.gitignore` sudah mengabaikan file sensitif tersebut.

## A. Siapkan database Supabase

1. Buat project baru di Supabase.
2. Buka **SQL Editor**.
3. Buka file `supabase_schema.sql` dari paket ini, salin seluruh isinya, lalu jalankan sekali.
4. Buka **Project Settings → API Keys**. Salin **Project URL** dan **Secret key** (`sb_secret_...`). Secret key hanya disimpan pada server/Streamlit Secrets.
5. Jangan gunakan publishable key untuk operasi admin aplikasi. Jangan pernah membagikan secret key lewat chat atau memasukkannya ke GitHub.

## B. Buat hash password admin

Pada komputer sendiri, ekstrak paket dan buka terminal di folder project:

```bash
python generate_admin_hash.py
```

Masukkan password admin minimal 12 karakter. Simpan nilai `ADMIN_PASSWORD_HASH` yang dicetak oleh program. Password mentah tidak perlu dikirim ke siapa pun.

## C. Upload source code ke GitHub

1. Buat repository baru di https://github.com/new. Nama yang disarankan: `mailguard-kelompok6`.
2. Repository **Public** memudahkan Streamlit Community Cloud mengaksesnya; source code dan model akan terlihat publik. Jangan pernah upload secrets. Repository Private juga dapat dipakai jika akses Streamlit Cloud sudah diberi izin.
3. Ekstrak ZIP paket deploy ini.
4. Upload isi folder project ke repository, bukan folder ZIP-nya. Pastikan `app.py` berada di root repository, sejajar dengan `requirements.txt`.
5. Sertakan folder `models/`, `.streamlit/config.toml`, `requirements.txt`, `supabase_schema.sql`, dan file `.py` lain.
6. **Jangan upload** `.streamlit/secrets.toml`, file `.db`, `.env`, atau password admin.

## D. Deploy ke Streamlit Community Cloud

1. Buka https://share.streamlit.io/ dan masuk/daftar.
2. Hubungkan akun GitHub dan izinkan Streamlit mengakses repository.
3. Klik **Create app**.
4. Pilih repository `mailguard-kelompok6`, branch `main`, dan main file path `app.py`.
5. Buka **Advanced settings**. Pilih Python **3.12**.
6. Pada field **Secrets**, tempel TOML berikut dan ganti placeholder dengan nilai dari akun milik sendiri:

```toml
ADMIN_PASSWORD_HASH = "pbkdf2_sha256$600000$GANTI_DENGAN_HASH_HASIL_GENERATOR"
SUPABASE_URL = "https://PROJECT_REF_ANDA.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_GANTI_DENGAN_SECRET_KEY_ANDA"
```

7. Klik **Deploy**. Tunggu proses instalasi package dan startup selesai.
8. Setelah URL `*.streamlit.app` muncul, buka link tersebut dan jalankan pengujian di bawah.

## E. Checklist sesudah deploy

- [ ] Halaman publik terbuka tanpa login.
- [ ] Kirim email contoh HAM; hasil HAM terlihat dan email masuk ke folder Inbox admin.
- [ ] Kirim email contoh SPAM; hasil SPAM terlihat dan email masuk ke folder Spam admin.
- [ ] Kode tracking dapat menampilkan status email pengirim tersebut.
- [ ] Kode tracking yang salah tidak menampilkan email.
- [ ] Login admin menerima password yang benar dan menolak password yang salah.
- [ ] Admin dapat melihat All Mail, Inbox, Spam, dan statistik.
- [ ] Kirim satu email uji, restart/redeploy aplikasi, lalu pastikan data tetap ada di Supabase.
- [ ] Dari browser biasa/incognito sebagai pengunjung, pastikan tidak ada akses ke daftar email atau dashboard admin.

## Catatan penting

- Kalau `SUPABASE_URL` dan `SUPABASE_SECRET_KEY` tidak diisi, aplikasi memakai SQLite lokal. Penyimpanan lokal pada hosting aplikasi tidak boleh dianggap permanen; aktifkan Supabase untuk database online.
- `sb_secret_...` memiliki hak akses penuh dan melewati Row Level Security. Simpan hanya di Streamlit Secrets, jangan commit ke GitHub, jangan tempel ke chat, dan rotasi jika pernah bocor.
- Form publik ini menerima data email sebagai simulasi. Aplikasi belum menerima email masuk langsung dari Gmail/Outlook melalui MX/SMTP dan belum meneruskan pesan ke alamat To.
- Aplikasi ini prototipe pembelajaran. Sebelum digunakan publik berskala besar, tambahkan CAPTCHA/anti-bot, rate limit jaringan, verifikasi email, kebijakan retensi data, backup, dan pemantauan.
