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
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except:
    st.error("API Key belum disetting!")
    st.stop()

model = genai.GenerativeModel("gemini-2.5-flash")

# --- 4. FUNGSI AUDIO (PEMBERSIH TEKS) ---
def play_audio(text):
    try:
        # Menghapus karakter latin/simbol agar gTTS hanya baca Hangul
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

# --- 5. SIDEBAR ---
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

# --- 7. TAMPILAN UTAMA ---
st.title("🎓 Guru Bahasa Korea AI")
st.write("Hanya melayani terjemahan Indonesia ↔ Korea.")

c = conn.cursor()
c.execute("SELECT id, role, content FROM messages WHERE session_id = ?", (st.session_state.current_session_id,))
current_messages = c.fetchall()

for m_id, role, content in current_messages:
    with st.chat_message(role):
        st.markdown(content)
        
        if role == "assistant" and "Maaf" not in content:
            # Mencari format [Korea | Romaji | Indo]
            variants = re.findall(r"\[(.*?)\]", content)
            if variants:
                for i, v in enumerate(variants):
                    # PROTEKSI ERROR: Cek apakah ada tanda '|'
                    parts = v.split("|")
                    
                    # Logika pengisian data yang aman (Index Safety)
                    korea = parts[0].strip() if len(parts) > 0 else "Error"
                    romaji = parts[1].strip() if len(parts) > 1 else ""
                    indo = parts[2].strip() if len(parts) > 2 else ""

                    # Tombol Audio (Hanya baca variabel 'korea')
                    if st.button(f"🔊 {korea}: {romaji}", key=f"aud_{m_id}_{i}"):
                        audio_fp = play_audio(korea)
                        if audio_fp:
                            st.audio(audio_fp, format="audio/mp3", autoplay=True)
                    
                    # Teks Bahasa Indonesia besar
                    if indo:
                        st.markdown(f"## {indo}")
                    st.write("---")

# --- 8. INPUT USER & PROMPT ---
if prompt := st.chat_input("Masukkan kata atau kalimat..."):
    c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
              (st.session_state.current_session_id, "user", prompt))
    conn.commit()
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Sedang merinci..."):
            instruction = (
                "Kamu adalah Guru Bahasa Korea. Jawab dengan ramah dan berikan penjelasan tata bahasa."
                "BATASAN: Hanya layani terjemahan Indonesia-Korea."
                "WAJIB FORMAT: Untuk setiap kata/kalimat Korea, gunakan [Teks Korea | Romanisasi | Arti Indonesia]. "
                "Contoh: [학교에 갑니다 | Hakgyoe gamnida | Pergi ke sekolah]."
            )
            
            try:
                response = model.generate_content(f"{instruction}\n\nSiswa: {prompt}")
                answer = response.text
                st.markdown(answer)
                
                # Simpan pesan & update judul
                c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
                          (st.session_state.current_session_id, "assistant", answer))
                conn.commit()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
