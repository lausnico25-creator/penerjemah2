import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import sqlite3
import io
import re
import random
import json
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
    st.error("API Key belum disetting di Secrets!")
    st.stop()

# Gunakan model yang stabil
model = genai.GenerativeModel("gemini-2.5-flash")

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

# --- 5. SIDEBAR & LOGIKA SESI ---
with st.sidebar:
    st.title("🇰🇷 Panel Kontrol")
    mode = st.radio("Pilih Mode:", ["Belajar & Tanya", "Roleplay Percakapan", "Kuis Berjenjang", "Konverter Angka"])
    
    st.write("---")
    if st.button("+ Chat Baru", use_container_width=True):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c = conn.cursor()
        c.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", ("Percakapan Baru", now))
        conn.commit()
        st.session_state.current_session_id = c.lastrowid
        # Reset kuis/roleplay saat pindah chat
        if 'curr_q' in st.session_state: del st.session_state.curr_q
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
                if st.session_state.get('current_session_id') == s_id:
                    st.session_state.current_session_id = None
                st.rerun()

# Pastikan ada session_id yang aktif
if "current_session_id" not in st.session_state or st.session_state.current_session_id is None:
    if sessions:
        st.session_state.current_session_id = sessions[0][0]
    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c = conn.cursor()
        c.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", ("Percakapan Baru", now))
        conn.commit()
        st.session_state.current_session_id = c.lastrowid

# --- 6. TAMPILAN UTAMA ---

if mode == "Belajar & Tanya":
    st.title("🎓 KA Tutor: Mode Belajar")
    
    # Load Pesan berdasarkan session aktif
    c = conn.cursor()
    c.execute("SELECT id, role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (st.session_state.current_session_id,))
    current_messages = c.fetchall()

    for m_id, role, content in current_messages:
        with st.chat_message(role):
            st.markdown(content)
            # Audio button auto-generator
            if role == "assistant" and "[" in content:
                matches = re.findall(r"\[(.*?)\|(.*?)\|(.*?)\]", content)
                for i, m in enumerate(matches):
                    if st.button(f"🔊 Play: {m[0].strip()}", key=f"aud_{m_id}_{i}"):
                        audio_fp = play_audio(m[0])
                        if audio_fp: st.audio(audio_fp, format="audio/mp3", autoplay=True)

    if prompt := st.chat_input("Tanya kata atau minta bedah kalimat..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Simpan pesan user
        c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, 'user', ?)", (st.session_state.current_session_id, prompt))
        conn.commit()

        instruction = (
            "Kamu adalah Guru Bahasa Korea yang ramah. "
            "Jika user memberi satu kata: berikan tabel perbandingan kesopanan (Banmal, Sopan, Formal). "
            "Jika user memberi kalimat: berikan 'BEDAH KALIMAT' (analisis subjek, objek, partikel). "
            "WAJIB FORMAT setiap kosakata kunci dengan: [Teks Korea | Romanisasi | Arti Indonesia]."
        )
        
        with st.spinner("Guru sedang menulis..."):
            response = model.generate_content(f"{instruction}\n\nSiswa: {prompt}")
            answer = response.text
            
            with st.chat_message("assistant"):
                st.markdown(answer)
            
            # Simpan pesan assistant
            c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, 'assistant', ?)", (st.session_state.current_session_id, answer))
            conn.commit()
            st.rerun()

elif mode == "Roleplay Percakapan":
    st.title("🎭 Simulator Roleplay")
    st.info("Latih percakapanmu! AI akan berperan sebagai lawan bicara.")

    col1, col2 = st.columns(2)
    with col1:
        skenario = st.selectbox("Situasi:", ["Bertemu Guru", "Pesan Makanan", "Tanya Jalan", "Kenalan di Cafe"])
    with col2:
        custom = st.text_input("Atau Skenario Sendiri:", placeholder="Contoh: Belanja di pasar...")

    situasi_final = custom if custom else skenario

    if st.button("Mulai Roleplay 🎬", use_container_width=True):
        st.session_state.roleplay_active = True
        sys_prompt = f"Skenario: {situasi_final}. Kamu (AI) adalah lawan bicara (Orang Kedua). User adalah Orang Pertama. Gunakan [Hangul | Romaji | Arti] di setiap balasan."
        st.session_state.rp_messages = [{"role": "system", "content": sys_prompt}]
        
        first_resp = model.generate_content(sys_prompt + " Mulailah percakapan!")
        st.session_state.rp_messages.append({"role": "assistant", "content": first_resp.text})

    if st.session_state.get("roleplay_active"):
        for m in st.session_state.rp_messages:
            if m["role"] != "system":
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])

        if rp_input := st.chat_input("Balas dalam Bahasa Korea/Indonesia..."):
            st.session_state.rp_messages.append({"role": "user", "content": rp_input})
            res = model.generate_content(str(st.session_state.rp_messages))
            st.session_state.rp_messages.append({"role": "assistant", "content": res.text})
            st.rerun()

        if st.button("Reset Roleplay 🔄"):
            del st.session_state.roleplay_active
            del st.session_state.rp_messages
            st.rerun()

elif mode == "Kuis Berjenjang":
    if 'q_level' not in st.session_state: st.session_state.q_level = "Mudah"
    if 'q_score' not in st.session_state: st.session_state.q_score = 0
    if 'q_step' not in st.session_state: st.session_state.q_step = 1
    if 'q_done' not in st.session_state: st.session_state.q_done = False
    
    levels = ["Mudah", "Sedang", "Susah", "Profesional"]

    # Header Atas
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1: st.title("🏆 Kuis Pintar")
    with c2: 
        lv = st.selectbox("Level:", levels, index=levels.index(st.session_state.q_level))
        if lv != st.session_state.q_level:
            st.session_state.q_level = lv; st.session_state.q_step = 1; st.session_state.q_score = 0
            if 'curr_q' in st.session_state: del st.session_state.curr_q
            st.rerun()
    with c3:
        if st.button("Reset 🔄", use_container_width=True):
            st.session_state.q_level = "Mudah"; st.session_state.q_score = 0; st.session_state.q_step = 1; st.session_state.q_done = False
            if 'curr_q' in st.session_state: del st.session_state.curr_q
            st.rerun()

    if st.session_state.q_done:
        st.balloons()
        st.success(f"### 🎉 Selesai! Skor: {st.session_state.q_score}/100")
        if st.button("Ulang / Lanjut", use_container_width=True):
            st.session_state.q_step = 1; st.session_state.q_score = 0; st.session_state.q_done = False
            if 'curr_q' in st.session_state: del st.session_state.curr_q
            st.rerun()
        st.stop()

    # Ambil riwayat untuk bahan kuis
    c = conn.cursor()
    c.execute("SELECT content FROM messages WHERE role='assistant' AND content LIKE '%|%' ORDER BY id DESC LIMIT 10")
    history_raw = c.fetchall()
    context_bahan = "\n".join([r[0] for r in history_raw])

    if 'curr_q' not in st.session_state:
        with st.spinner("Merancang soal..."):
            source = f"Gunakan riwayat ini: {context_bahan}" if history_raw else "Gunakan kosakata umum"
            prompt_q = (
                f"{source}\nBuat 1 soal kuis Korea {st.session_state.q_level}. "
                "HANYA JSON: {\"q\": \"soal\", \"r\": \"cara baca\", \"a\": \"jawaban benar\", \"o\": [\"salah1\", \"salah2\", \"salah3\"]}"
            )
            try:
                res = model.generate_content(prompt_q)
                data = json.loads(re.search(r'\{.*\}', res.text, re.DOTALL).group())
                opts = data['o'] + [data['a']]; random.shuffle(opts)
                st.session_state.curr_q = {"q": data['q'], "r": data['r'], "a": data['a'], "opts": opts}
            except: 
                st.error("Gagal memuat soal."); st.button("Refresh"); st.stop()

    st.write(f"**Soal {st.session_state.q_step} / 5**")
    st.progress(st.session_state.q_step / 5)
    q = st.session_state.curr_q
    st.subheader(q['q'])
    st.caption(f"Baca: {q['r']}")
    ans = st.radio("Pilih jawaban:", q['opts'], index=None, key=f"q_{st.session_state.q_step}")

    if st.button("Kirim Jawaban", use_container_width=True):
        if ans == q['a']:
            st.success("Benar! +20"); st.session_state.q_score += 20
        else: st.error(f"Salah! Jawaban: {q['a']}")
        
        if st.session_state.q_step < 5:
            st.session_state.q_step += 1; del st.session_state.curr_q; st.rerun()
        else:
            st.session_state.q_done = True; st.rerun()

elif mode == "Konverter Angka":
    st.title("🔢 Konverter Angka")
    num = st.number_input("Input Angka:", min_value=1)
    if st.button("Konversi"):
        res = model.generate_content(f"Konversi angka {num} ke Sino dan Native Korea beserta cara baca.")
        st.write(res.text)
