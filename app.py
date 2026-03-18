import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import sqlite3
import io
import re
import random
from datetime import datetime

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Tutor Korea AI Pro", page_icon="🇰🇷", layout="wide")

# --- 2. DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('database_korea.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sessions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, role TEXT, content TEXT)''')
    conn.commit()
    return conn

conn = init_db()

# --- 3. KONFIGURASI API ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("API Key belum disetting!")
    st.stop()

model = genai.GenerativeModel("gemini-2.5-flash") # Update ke model terbaru

# --- 4. FUNGSI PENDUKUNG ---
def play_audio(text):
    try:
        korean_only = re.sub(r'[^가-힣\s]', '', text)
        if not korean_only.strip():
            return None
        tts = gTTS(text=korean_only, lang='ko')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except:
        return None

def get_quiz_data():
    c = conn.cursor()
    c.execute("SELECT content FROM messages WHERE role='assistant' LIMIT 20")
    data = c.fetchall()
    words = []
    for entry in data:
        found = re.findall(r"\[(.*?)\|(.*?)\|(.*?)\]", entry[0])
        words.extend(found)
    return list(set(words)) # Unik

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🇰🇷 Panel Kontrol")
    
    # Mode Belajar
    mode = st.radio("Pilih Mode:", ["Belajar & Tanya", "Roleplay Percakapan", "Kuis Kosakata", "Konverter Angka"])
    
    st.write("---")
    if st.button("+ Chat Baru", use_container_width=True):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c = conn.cursor()
        c.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", ("Percakapan Baru", now))
        conn.commit()
        st.session_state.current_session_id = c.lastrowid
        st.rerun()

    st.write("### Riwayat Belajar")
    c = conn.cursor()
    c.execute("SELECT id, title FROM sessions ORDER BY id DESC")
    sessions = c.fetchall()
    for s_id, s_title in sessions:
        col_chat, col_del = st.columns([4, 1])
        with col_chat:
            if st.button(f"📄 {s_title}", key=f"s_{s_id}", use_container_width=True):
                st.session_state.current_session_id = s_id
                st.rerun()
        with col_del:
            if st.button("🗑️", key=f"del_{s_id}"):
                c.execute("DELETE FROM sessions WHERE id = ?", (s_id,))
                c.execute("DELETE FROM messages WHERE session_id = ?", (s_id,))
                conn.commit()
                st.session_state.current_session_id = None
                st.rerun()

# --- 6. LOGIKA SESI ---
if "current_session_id" not in st.session_state or st.session_state.current_session_id is None:
    if sessions:
        st.session_state.current_session_id = sessions[0][0]
    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c = conn.cursor()
        c.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", ("Percakapan Baru", now))
        conn.commit()
        st.session_state.current_session_id = c.lastrowid

# --- 7. TAMPILAN UTAMA BERDASARKAN MODE ---

if mode == "Belajar & Tanya":
    st.title("🎓 KA Tutor: Mode Belajar")
    
    c = conn.cursor()
    c.execute("SELECT id, role, content FROM messages WHERE session_id = ?", (st.session_state.current_session_id,))
    current_messages = c.fetchall()

    for m_id, role, content in current_messages:
        with st.chat_message(role):
            st.markdown(content)
            if role == "assistant" and "[" in content:
                variants = re.findall(r"\[(.*?)\]", content)
                for i, v in enumerate(variants):
                    parts = v.split("|")
                    if len(parts) >= 3:
                        korea, romaji, indo = parts[0].strip(), parts[1].strip(), parts[2].strip()
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            if st.button(f"🔊 Play", key=f"aud_{m_id}_{i}"):
                                audio_fp = play_audio(korea)
                                if audio_fp: st.audio(audio_fp, format="audio/mp3", autoplay=True)
                        with col2:
                            st.caption(f"**{korea}** ({romaji}): {indo}")

    if prompt := st.chat_input("Tanya kata atau minta bedah kalimat..."):
        # Logika Prompt Sama dengan kode asli namun diperkuat instruksinya
        instruction = (
            "Kamu adalah Guru Bahasa Korea. Jika user memberi satu kata, berikan tabel perbandingan kesopanan dan waktu. "
            "Jika user memberi kalimat panjang, berikan 'BEDAH KALIMAT' (analisis subjek, objek, partikel). "
            "WAJIB FORMAT: [Teks Korea | Romanisasi | Arti Indonesia] untuk kata kunci."
        )
        # (Bagian eksekusi Gemini & database tetap sama seperti kodemu sebelumnya)
        # ... (Gunakan logika pemrosesan prompt di kode asli kamu di sini)

elif mode == "Roleplay Percakapan":
    st.title("🎭 Mode Roleplay")
    st.info("Pilih situasi dan bicaralah dengan AI seolah-olah kamu di Korea!")
    situasi = st.selectbox("Pilih Situasi:", ["Di Restoran", "Tanya Jalan", "Kenalan di Kampus", "Belanja di Myeongdong"])
    
    if st.button("Mulai Roleplay"):
        with st.chat_message("assistant"):
            resp = model.generate_content(f"Mulailah percakapan pendek dalam bahasa Korea sebagai orang lokal dalam situasi {situasi}. Berikan terjemahan di bawahnya.")
            st.markdown(resp.text)

elif mode == "Kuis Kosakata":
    st.title("🧠 Kuis Cerdas Tangkas")
    quiz_data = get_quiz_data()
    if len(quiz_data) < 3:
        st.warning("Belum cukup data untuk kuis. Silakan mengobrol dulu di mode 'Belajar'!")
    else:
        q = random.choice(quiz_data)
        st.subheader(f"Apa arti dari: **{q[0]}** ({q[1]})?")
        ans = st.radio("Pilih jawaban:", [q[2], "Salah satu arti lain", "Tidak tahu"])
        if st.button("Cek Jawaban"):
            if ans == q[2]: st.success("Benar! Hebat!")
            else: st.error(f"Salah. Jawaban yang benar adalah {q[2]}")

elif mode == "Konverter Angka":
    st.title("🔢 Konverter Angka Korea")
    num_input = st.number_input("Masukkan Angka:", min_value=1, max_value=1000000)
    if st.button("Konversi"):
        res = model.generate_content(f"Tuliskan angka {num_input} dalam sistem angka Sino-Korean dan Native-Korean beserta cara bacanya (Hangul & Romaji).")
        st.write(res.text)

# --- RE-RUN LOGIC UNTUK INPUT (Copied from your original) ---
if mode == "Belajar & Tanya" and prompt:
    # (Copy paste bagian pemrosesan prompt dari kode aslimu ke sini untuk menjalankan logicnya)
    try:
        response = model.generate_content(f"{instruction}\n\nSiswa: {prompt}")
        answer = response.text
        c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
                  (st.session_state.current_session_id, "assistant", answer))
        conn.commit()
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")
