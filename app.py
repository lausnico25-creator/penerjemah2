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
        st.warning("Belum cukup data. Ngobrol dulu di mode 'Belajar' agar AI punya bahan kuis!")
    else:
        # Gunakan session_state agar soal tidak berubah saat klik tombol
        if 'current_quiz' not in st.session_state:
            q = random.choice(quiz_data)
            
            # Minta Gemini bikin pilihan jebakan yang mirip
            distractor_gen = model.generate_content(
                f"Berikan 3 jawaban salah yang mirip/terkait dalam Bahasa Indonesia untuk kata Korea '{q[0]}' yang artinya '{q[2]}'. "
                "Hanya berikan 3 kata/frasa dipisahkan koma, tanpa penjelasan."
            )
            distractors = distractor_gen.text.strip().split(",")
            
            options = [q[2]] + [d.strip() for d in distractors]
            random.shuffle(options)
            
            st.session_state.current_quiz = {"q": q, "options": options}

        quiz = st.session_state.current_quiz
        st.subheader(f"Apa arti dari: **{quiz['q'][0]}**?")
        st.caption(f"Cara baca: {quiz['q'][1]}")
        
        ans = st.radio("Pilih jawaban yang paling tepat:", quiz['options'], index=None)
        
        col_cek, col_next = st.columns(2)
        with col_cek:
            if st.button("Cek Jawaban", use_container_width=True):
                if ans == quiz['q'][2]:
                    st.success(f"✅ Benar! {quiz['q'][0]} memang berarti {quiz['q'][2]}.")
                    st.balloons()
                else:
                    st.error(f"❌ Salah! Jawaban yang benar adalah: {quiz['q'][2]}")
        
        with col_next:
            if st.button("Soal Selanjutnya ➡️", use_container_width=True):
                del st.session_state.current_quiz
                st.rerun()


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
