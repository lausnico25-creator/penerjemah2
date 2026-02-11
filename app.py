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
    st.error("API Key belum disetting di Secrets!")
    st.stop()

model = genai.GenerativeModel("gemini-2.5-flash")

# --- 4. FUNGSI AUDIO ---
def play_audio(text):
    try:
        # Hanya ambil bagian Hangul untuk suara
        korean_text = re.sub(r'[^가-힣\s]', '', text)
        if not korean_text.strip(): return None
        
        tts = gTTS(text=korean_text, lang='ko')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except:
        return None

# --- 5. SIDEBAR: RIWAYAT ---
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
            # Pola: [Korea | Romanisasi | Arti]
            variants = re.findall(r"\[(.*?)\]", content)
            if variants:
                for i, v in enumerate(variants):
                    if "|" in v:
                        parts = v.split("|")
                        korea = parts[0].strip()
                        romaji = parts[1].strip()
                        indo = parts[2].strip()
                    else:
                        continue

                    # --- TAMPILAN SESUAI GAMBAR ---
                    # Baris 1: Tombol Audio (Korea + Romaji)
                    if st.button(f"🔊 {korea}: {romaji}", key=f"aud_{m_id}_{i}"):
                        audio_fp = play_audio(korea)
                        if audio_fp:
                            st.audio(audio_fp, format="audio/mp3", autoplay=True)
                    
                    # Baris 2: Arti Bahasa Indonesia (Teks Besar & Tebal)
                    st.markdown(f"## {indo}")
                    st.write("") # Spasi

# --- 8. INPUT USER & PROMPT ---
if prompt := st.chat_input("Masukkan kata atau kalimat..."):
    c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
              (st.session_state.current_session_id, "user", prompt))
    conn.commit()
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Sedang merinci..."):
            # Prompt untuk memaksa format dan membatasi topik
            instruction = (
                "Kamu adalah Guru Bahasa Korea. "
                "BATASAN: Hanya jawab jika terkait terjemahan Indonesia ke Korea atau sebaliknya. "
                "Jika di luar itu, jawab: 'Maaf, saya hanya khusus melayani terjemahan Indonesia-Korea.' "
                "WAJIB FORMAT: [Korea | Romanisasi | Arti]. "
                "Contoh: [먹습니다 | Meokseumnida | makan]."
            )
            
            try:
                response = model.generate_content(f"{instruction}\n\nSiswa: {prompt}")
                answer = response.text
                st.markdown(answer)
                
                # Update judul chat
                c.execute("SELECT title FROM sessions WHERE id = ?", (st.session_state.current_session_id,))
                if c.fetchone()[0] == "Percakapan Baru":
                    res_title = model.generate_content(f"Judul 2 kata untuk: {prompt}")
                    c.execute("UPDATE sessions SET title = ? WHERE id = ?", (res_title.text[:20].strip(), st.session_state.current_session_id))
                
                c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
                          (st.session_state.current_session_id, "assistant", answer))
                conn.commit()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
