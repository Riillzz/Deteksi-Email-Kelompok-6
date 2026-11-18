# Email Detection — Sistem Deteksi Email Spam

Prototype aplikasi Machine Learning untuk mengklasifikasikan email ke dalam dua kategori, yaitu **HAM** dan **SPAM**.

Project ini dikembangkan oleh Kelompok 6 untuk memenuhi tugas mata kuliah Aplikasi Machine Learning, Fakultas Teknik, Universitas Singaperbangsa Karawang.

Aplikasi menggunakan algoritma **Logistic Regression** dengan ekstraksi fitur **Term Frequency–Inverse Document Frequency (TF-IDF)** berdasarkan model hasil eksperimen kelompok.

## 1. Gambaran Umum

Email Detection merupakan prototype sederhana untuk membantu pengguna mengenali email yang berpotensi termasuk spam.

Pengguna dapat memasukkan subjek dan isi email ke dalam aplikasi. Selanjutnya, sistem akan mengolah teks tersebut menggunakan TF-IDF dan melakukan klasifikasi menggunakan Logistic Regression.

Hasil klasifikasi ditampilkan dalam bentuk:

- HAM: Email dikategorikan sebagai pesan yang bukan spam.
- SPAM: Email dikategorikan sebagai pesan spam.
- Probabilitas spam: Estimasi kemungkinan email termasuk kategori spam.

Prototype ini menggunakan model yang telah dilatih sebelumnya sehingga tidak melakukan proses training ulang setiap kali aplikasi dijalankan.

## 2. Fitur Aplikasi

Fitur utama yang tersedia pada aplikasi:

1. **Input Subject**  
   Pengguna dapat memasukkan subjek email yang ingin diperiksa.

2. **Input Message**  
   Pengguna dapat memasukkan isi atau teks email.

3. **Klasifikasi Email**  
   Sistem melakukan prediksi untuk menentukan apakah email termasuk HAM atau SPAM.

4. **Probabilitas Spam**  
   Sistem menampilkan estimasi probabilitas email termasuk spam dalam bentuk persentase.

5. **Validasi Input**  
   Sistem memberikan peringatan apabila pengguna mengirimkan input kosong.

6. **Informasi Model**  
   Aplikasi menyediakan informasi mengenai algoritma dan konfigurasi yang digunakan dalam penelitian.

## 3. Metode Machine Learning

Penelitian ini menggunakan Enron Spam Dataset versi CSV sebagai sumber data.

Karakteristik dataset penelitian:

| Keterangan | Jumlah |
|---|---:|
| Dataset awal | 33.716 email |
| Data setelah pembersihan | 30.105 email |
| Sampel penelitian | 5.000 email |
| Email HAM | 2.500 |
| Email SPAM | 2.500 |
| Bahasa | Inggris |

### Pembagian Dataset

Dataset dibagi menggunakan metode stratified splitting dengan perbandingan 70:15:15.

| Jenis Data | Jumlah | Persentase |
|---|---:|---:|
| Training | 3.500 | 70% |
| Validation | 750 | 15% |
| Testing | 750 | 15% |
| Total | 5.000 | 100% |

### Preprocessing Data

Sebelum dilakukan ekstraksi fitur, teks email melalui beberapa tahapan preprocessing:

1. Menggabungkan Subject dan Message.
2. Case folding atau mengubah huruf menjadi lowercase.
3. Mengganti URL dengan token `urltoken`.
4. Mengganti alamat email dengan token `emailtoken`.
5. Menangani karakter non-ASCII.
6. Melakukan normalisasi spasi dan baris baru.

Stopwords tidak dihapus dan stemming tidak diterapkan.

### Ekstraksi Fitur TF-IDF

TF-IDF digunakan untuk mengubah teks email menjadi representasi numerik agar dapat diproses oleh algoritma klasifikasi.

Konfigurasi yang digunakan:

| Parameter | Nilai |
|---|---|
| ngram_range | (1, 1) |
| min_df | 2 |
| max_df | 1.0 |
| max_features | 5000 |
| norm | l2 |
| stop_words | None |
| lowercase | True |

### Algoritma Logistic Regression

Penelitian melakukan pengujian terhadap tiga variasi parameter regularisasi:

| Konfigurasi | Nilai C |
|---|---:|
| LR-1 | 0,1 |
| LR-2 | 1,0 |
| LR-3 | 10,0 |

Berdasarkan hasil validasi, konfigurasi LR-3 dengan C = 10,0 memperoleh F1-score spam tertinggi sehingga dipilih sebagai model final.

Konfigurasi model final:

- Algorithm: Logistic Regression
- Penalty: L2
- Solver: liblinear
- C: 10.0
- Max iteration: 1000
- Random state: 42

### Threshold Klasifikasi

Penentuan kategori email menggunakan threshold sebesar 0,5.

- HAM: Probabilitas spam < 0,5.
- SPAM: Probabilitas spam ≥ 0,5.

## 4. Hasil Evaluasi Model

Berdasarkan evaluasi akhir terhadap 750 data testing, model Logistic Regression dengan C = 10,0 memperoleh hasil sebagai berikut:

| Metrik | Hasil |
|---|---:|
| Accuracy | 98,53% |
| Precision Spam | 97,64% |
| Recall Spam | 99,47% |
| F1-score Spam | 98,55% |

Confusion matrix model final:

| | Prediksi HAM | Prediksi SPAM |
|---|---:|---:|
| Aktual HAM | 366 | 9 |
| Aktual SPAM | 2 | 373 |

Model berhasil mengklasifikasikan 739 dari 750 email dengan benar.

Hasil tersebut menunjukkan bahwa model mampu membedakan email HAM dan SPAM dengan baik pada dataset pengujian yang digunakan.

## 5. Prototipe Prediksi

Prototype menggunakan model dan vectorizer yang telah disimpan dalam format Joblib.

File model dimuat kembali ketika aplikasi dijalankan sehingga pengguna dapat melakukan prediksi terhadap email baru tanpa melakukan training ulang.

Alur proses aplikasi:

```text
Pengguna
   |
   v
Input Subject dan Message
   |
   v
Validasi Input
   |
   v
Preprocessing Text
   |
   v
Ekstraksi Fitur TF-IDF
   |
   v
Logistic Regression (C = 10)
   |
   v
Perhitungan Probabilitas Spam
   |
   v
Threshold 0,5
   |
   v
Hasil Klasifikasi
   |
   +------ HAM
   |
   +------ SPAM
```

### Pengujian Prototype

Prototype diuji menggunakan sepuluh skenario, yaitu:

1. Input kosong.
2. Email HAM berupa agenda rapat.
3. Email HAM berupa balasan terkait kontrak.
4. Email HAM berupa jadwal bimbingan.
5. Email HAM berupa pemberitahuan beasiswa.
6. Email SPAM berupa penawaran hadiah.
7. Email SPAM berupa penawaran penurunan berat badan.
8. Email SPAM berupa phishing akun.
9. Email SPAM berupa penawaran investasi.
10. Email SPAM berbahasa Indonesia.

Pengujian tersebut digunakan untuk melihat respons aplikasi terhadap berbagai bentuk input email baru.

Hasil pengujian dan pembahasannya dijelaskan lebih lanjut pada Bab IV bagian G dalam laporan penelitian.

## 6. Keterbatasan Sistem

Prototype ini memiliki beberapa keterbatasan:

- Dataset yang digunakan didominasi email berbahasa Inggris.
- Model belum secara khusus dilatih menggunakan email akademik perguruan tinggi di Indonesia.
- Kata dan konteks dalam email dapat memengaruhi hasil klasifikasi.
- Email yang menggunakan penyamaran kata atau obfuscation berpotensi sulit dikenali.
- Probabilitas yang ditampilkan merupakan estimasi keluaran model dan belum tentu terkalibrasi.
- Hasil klasifikasi bukan jaminan bahwa suatu email aman atau berbahaya.

Oleh karena itu, hasil prediksi sebaiknya digunakan sebagai informasi pendukung dan bukan satu-satunya dasar dalam menentukan keamanan email.

## 7. Struktur Project

```text
Email-Detection/
│
├── app.py
├── predictor.py
├── requirements.txt
│
├── models/
│   ├── logistic_regression_kelompok6.joblib
│   └── tfidf_vectorizer_kelompok6.joblib
│
└── README.md
```

File utama:

| File | Fungsi |
|---|---|
| app.py | Menampilkan antarmuka aplikasi Streamlit |
| predictor.py | Memuat model, preprocessing, dan melakukan prediksi |
| requirements.txt | Daftar library yang dibutuhkan |
| models/ | Menyimpan model Logistic Regression dan TF-IDF |
| README.md | Dokumentasi project |

Beberapa file pendukung dari pengembangan versi sebelumnya dapat tetap berada di repository, tetapi tidak digunakan oleh prototype sederhana ini.

## 8. Instalasi dan Menjalankan Aplikasi

### Persyaratan

- Python 3.11 atau versi yang kompatibel.
- Pip.
- Library Streamlit.
- Library Scikit-learn.
- Library Joblib.

### Langkah Menjalankan Aplikasi

1. Clone repository:

```bash
git clone https://github.com/USERNAME/REPOSITORY.git
```

2. Masuk ke direktori project:

```bash
cd REPOSITORY
```

3. Instal seluruh library:

```bash
pip install -r requirements.txt
```

4. Jalankan aplikasi:

```bash
streamlit run app.py
```

5. Buka alamat lokal yang ditampilkan pada terminal, biasanya:

```text
http://localhost:8501
```

## 9. Deployment

Aplikasi menggunakan Streamlit Community Cloud untuk deployment sehingga dapat diakses melalui browser.

Repository GitHub berfungsi sebagai sumber kode aplikasi.

Setelah perubahan kode di-push ke branch yang terhubung dengan Streamlit Community Cloud, aplikasi akan diperbarui secara otomatis.

Pastikan folder `models/` dan file `requirements.txt` ikut tersedia di repository agar aplikasi dapat berjalan dengan baik.

## 10. Teknologi yang Digunakan

- Python
- Streamlit
- Scikit-learn
- TF-IDF
- Logistic Regression
- Joblib
- GitHub
- Streamlit Community Cloud

## 11. Tim Pengembang

**Kelompok 6**

Mata Kuliah: Aplikasi Machine Learning  
Fakultas Teknik  
Universitas Singaperbangsa Karawang

Anggota:

1. Aril Yudatmo
2. Ahmad Beril Munajat
3. Argya Wahono
4. Aufa Nur Azizah
5. Ayu Adinda Putri Nabilla

---

**Email Detection — Sistem Deteksi Email Spam**

Project Machine Learning Kelompok 6 | 2026