import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import sqlite3
import io
import re
from datetime import datetime

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Tutor Korea-Indo AI", page_icon="🇰🇷", layout="wide")

# --- DATABASE SETUP ---
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

# --- KONFIGURASI API ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("API Key belum disetting di Secrets!")
    st.stop()

model = genai.GenerativeModel("gemini-2.5-flash")

# --- FUNGSI AUDIO ---
def play_audio(text):
    try:
        # Hanya memproses teks jika tidak kosong
        if not text.strip():
            return None
        tts = gTTS(text=text, lang='ko')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        return None

# --- SIDEBAR: RIWAYAT CHAT ---
with st.sidebar:
    st.title("🇰🇷 Riwayat Belajar")
    
    # PERBAIKAN: Tombol Chat Baru
    if st.button("+ Chat Baru", use_container_width=True):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c = conn.cursor()
        # Buat sesi baru di database
        c.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", ("Percakapan Baru", now))
        conn.commit()
        # Langsung set ID sesi aktif ke yang baru saja dibuat
        st.session_state.current_session_id = c.lastrowid
        # Paksa Streamlit refresh agar layar kosong (mulai chat baru)
        st.rerun()

    st.write("---")
    c = conn.cursor()
    c.execute("SELECT id, title FROM sessions ORDER BY id DESC")
    sessions = c.fetchall()
    
    for s_id, s_title in sessions:
        if st.button(f"📄 {s_title}", key=f"s_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            st.rerun()

# --- LOGIKA SESI (Pastikan ID selalu valid) ---
if "current_session_id" not in st.session_state:
    if sessions:
        st.session_state.current_session_id = sessions[0][0]
    else:
        # Jika benar-benar kosong, buat satu
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c = conn.cursor()
        c.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", ("Percakapan Baru", now))
        conn.commit()
        st.session_state.current_session_id = c.lastrowid

# --- TAMPILAN UTAMA ---
st.title("🎓 Guru Bahasa Korea AI")
st.caption("Fokus: Audio hanya pada kata Korea")

# Ambil history dari DB
c = conn.cursor()
c.execute("SELECT id, role, content FROM messages WHERE session_id = ?", (st.session_state.current_session_id,))
current_messages = c.fetchall()

for m_id, role, content in current_messages:
    with st.chat_message(role):
        st.markdown(content)
        
        if role == "assistant":
            # Mencari teks yang berada di dalam kurung siku [ ] menggunakan Regex
            # Contoh: "Bahasa Koreanya makan adalah [먹다]" -> akan mengambil "먹다"
            korean_words = re.findall(r"\[(.*?)\]", content)
            
            if korean_words:
                # Jika ada banyak kata, kita ambil yang pertama atau gabungkan
                word_to_speak = ", ".join(korean_words)
                if st.button(f"🔊 Dengar Pengucapan: {word_to_speak}", key=f"audio_{m_id}"):
                    with st.spinner("Menyiapkan audio..."):
                        audio_fp = play_audio(word_to_speak)
                        if audio_fp:
                            st.audio(audio_fp, format="audio/mp3")

# --- INPUT USER ---
if prompt := st.chat_input("Tanya guru..."):
    c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
              (st.session_state.current_session_id, "user", prompt))
    conn.commit()
    
    # Update Judul Otomatis
    c.execute("SELECT title FROM sessions WHERE id = ?", (st.session_state.current_session_id,))
    if c.fetchone()[0] == "Percakapan Baru":
        res_title = model.generate_content(f"Judul chat 2 kata untuk: {prompt}")
        c.execute("UPDATE sessions SET title = ? WHERE id = ?", (res_title.text.strip(), st.session_state.current_session_id))
        conn.commit()

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Guru sedang merespons..."):
            # INSTRUKSI KHUSUS: Gunakan tanda kurung siku untuk kata Korea
            instruction = (
                "Kamu adalah Guru Bahasa Korea. "
                "PENTING: Setiap kali kamu menuliskan kata atau kalimat Korea yang utama, "
                "WAJIB mengapitnya dengan kurung siku, contoh: [안녕하세요]. "
                "Berikan penjelasan dalam Bahasa Indonesia yang ramah."
            )
            response = model.generate_content(f"{instruction}\n\nSiswa: {prompt}")
            answer = response.text
            st.markdown(answer)
            
            c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
                      (st.session_state.current_session_id, "assistant", answer))
            conn.commit()
    st.rerun()
