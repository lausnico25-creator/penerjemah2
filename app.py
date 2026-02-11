import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import sqlite3
import io
import re
from datetime import datetime

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Tutor Korea AI", page_icon="🇰🇷", layout="wide")

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
    # Pastikan "GEMINI_API_KEY" sudah ada di .streamlit/secrets.toml atau Secrets Streamlit Cloud
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.error("API Key belum disetting di Secrets! Pastikan GEMINI_API_KEY tersedia.")
    st.stop()

# Menggunakan model terbaru (sesuai ketersediaan, default gemini-1.5-flash)
model = genai.GenerativeModel("gemini-2.5-flash")

# --- 4. FUNGSI AUDIO ---
def play_audio(text):
    try:
        # Menghapus karakter non-Korea agar pelafalan gTTS lebih akurat
        clean_text = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', text)
        tts = gTTS(text=clean_text, lang='ko')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception:
        return None

# --- 5. SIDEBAR: RIWAYAT & MANAJEMEN SESI ---
with st.sidebar:
    st.title("🇰🇷 Riwayat Belajar")
    
    if st.button("+ Chat Baru", use_container_width=True):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c = conn.cursor()
        c.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", ("Percakapan Baru", now))
        conn.commit()
        st.session_state.current_session_id = c.lastrowid
        st.rerun()

    st.write("---")
    
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

# --- 6. LOGIKA SESI AKTIF ---
if "current_session_id" not in st.session_state or st.session_state.current_session_id is None:
    if sessions:
        st.session_state.current_session_id = sessions[0][0]
    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c = conn.cursor()
        c.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", ("Percakapan Baru", now))
        conn.commit()
        st.session_state.current_session_id = c.lastrowid

# --- 7. TAMPILAN UTAMA ---
st.title("🎓 Guru Bahasa Korea AI")

c = conn.cursor()
c.execute("SELECT id, role, content FROM messages WHERE session_id = ?", (st.session_state.current_session_id,))
current_messages = c.fetchall()

# Menampilkan pesan chat
for m_id, role, content in current_messages:
    with st.chat_message(role):
        st.markdown(content)
        
        if role == "assistant":
            # Mencari teks di dalam kurung siku [...]
            variants = re.findall(r"\[(.*?)\]", content)
            if variants:
                st.write("🔈 **Kosa Kata:**")
                for i, v in enumerate(variants):
                    # Memisahkan Kata Korea dan Artinya jika ada tanda ":"
                    if ":" in v:
                        korea_word, meaning = v.split(":", 1)
                        korea_word = korea_word.strip()
                        meaning = meaning.strip()
                    else:
                        korea_word = v.strip()
                        meaning = ""

                    # Tampilan Tombol Audio dan Penjelasan
                    col_btn, col_txt = st.columns([1, 4])
                    with col_btn:
                        if st.button(f"🔊 {korea_word}", key=f"aud_{m_id}_{i}"):
                            audio_fp = play_audio(korea_word)
                            if audio_fp:
                                st.audio(audio_fp, format="audio/mp3", autoplay=True)
                    with col_txt:
                        if meaning:
                            st.info(f"Artinya: {meaning}")

# --- 8. INPUT USER & RESPON AI ---
if prompt := st.chat_input("Tanya guru (contoh: Apa bahasa Koreanya makan?)"):
    # Simpan pesan user ke DB
    c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
              (st.session_state.current_session_id, "user", prompt))
    conn.commit()
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Guru sedang merinci..."):
            try:
                # Instruksi agar AI memberikan format [Korea: Arti]
                instruction = (
                    "Kamu adalah Guru Bahasa Korea yang ramah. "
                    "WAJIB: Setiap kali menyebutkan kata Korea penting, tulis dalam kurung siku dengan format [Kata Korea: Arti]. "
                    "Contoh: [먹다: Makan]. Berikan penjelasan dalam Bahasa Indonesia yang mudah dipahami."
                )
                
                response = model.generate_content(f"{instruction}\n\nSiswa: {prompt}")
                answer = response.text
                st.markdown(answer)
                
                # Update Judul Chat Otomatis jika masih default
                c.execute("SELECT title FROM sessions WHERE id = ?", (st.session_state.current_session_id,))
                current_title = c.fetchone()
                if current_title and current_title[0] == "Percakapan Baru":
                    res_title = model.generate_content(f"Buatkan judul singkat (max 3 kata) untuk topik ini: {prompt}")
                    clean_title = res_title.text.strip().replace('"', '')
                    c.execute("UPDATE sessions SET title = ? WHERE id = ?", (clean_title, st.session_state.current_session_id))
                
                # Simpan pesan assistant ke DB
                c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
                          (st.session_state.current_session_id, "assistant", answer))
                conn.commit()
                st.rerun()
                
            except Exception as e:
                if "ResourceExhausted" in str(e):
                    st.warning("Kuota harian API habis. Silakan coba lagi nanti.")
                else:
                    st.error(f"Terjadi kesalahan: {e}")
