import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import sqlite3
import io
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
        # Kita deteksi jika teks mengandung hangeul, gunakan lang 'ko'
        # Jika tidak, gTTS biasanya otomatis atau kita set ke 'ko' karena ini tutor Korea
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
        if st.button(f"📄 {s_title}", key=f"s_{s_id}", use_container_width=True):
            st.session_state.current_session_id = s_id
            st.rerun()

# --- LOGIKA SESI ---
if "current_session_id" not in st.session_state or st.session_state.current_session_id is None:
    if sessions:
        st.session_state.current_session_id = sessions[0][0]
    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c = conn.cursor()
        c.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", ("Percakapan Baru", now))
        conn.commit()
        st.session_state.current_session_id = c.lastrowid

# --- TAMPILAN UTAMA ---
st.title("🎓 Guru Bahasa Korea AI")
st.caption("Fitur: Pilih Bentuk Kata untuk Audio")

# Ambil history dari DB
c = conn.cursor()
c.execute("SELECT id, role, content FROM messages WHERE session_id = ?", (st.session_state.current_session_id,))
current_messages = c.fetchall()

# Menampilkan chat
for m_id, role, content in current_messages:
    with st.chat_message(role):
        st.markdown(content)
        
        # Logika Audio Terpisah untuk jawaban Guru
        if role == "assistant":
            # Mencari semua kata di dalam kurung siku [ ]
            # Contoh: "Bentuk dasar: [먹다], Bentuk formal: [먹습니다]"
            korean_variants = re.findall(r"\[(.*?)\]", content)
            
            if korean_variants:
                st.write("---")
                st.write("🔈 **Pilih kata untuk didengar:**")
                
                # Membuat kolom agar tombol-tombolnya berjejer rapi
                cols = st.columns(len(korean_variants))
                
                for i, word in enumerate(korean_variants):
                    with cols[i]:
                        if st.button(f"🔊 {word}", key=f"audio_{m_id}_{i}"):
                            with st.spinner("..."):
                                audio_fp = play_audio(word)
                                if audio_fp:
                                    st.audio(audio_fp, format="audio/mp3")

# --- INPUT USER ---
if prompt := st.chat_input("Tanya guru..."):
    # Simpan pesan user
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
        with st.spinner("Guru sedang merinci bentuk kata..."):
            # INSTRUKSI: AI harus membungkus setiap bentuk kata Korea dengan [ ]
            instruction = (
                "Kamu adalah Guru Bahasa Korea. Jika siswa bertanya tentang kata kerja atau kalimat, "
                "berikan beberapa bentuk (contoh: Dasar, Sopan, Formal). "
                "WAJIB: Setiap kata Korea tersebut harus diapit kurung siku, contoh: [먹다], [먹어요], [먹습니다]. "
                "Berikan penjelasan singkat dalam Bahasa Indonesia."
            )
            response = model.generate_content(f"{instruction}\n\nSiswa: {prompt}")
            answer = response.text
            st.markdown(answer)
            
            c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", 
                      (st.session_state.current_session_id, "assistant", answer))
            conn.commit()
    st.rerun()
