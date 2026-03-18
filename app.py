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
st.set_page_config(page_title="KA Tutor Korea Pro", page_icon="🇰🇷", layout="wide")

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

# --- 4. FUNGSI PENDUKUNG ---
def play_audio(text):
    try:
        korean_only = re.sub(r'[^가-힣\s]', '', text)
        if not korean_only.strip(): return None
        tts = gTTS(text=korean_only, lang='ko')
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except: return None

# --- 5. SIDEBAR & LOGIKA NAVIGASI ---
with st.sidebar:
    st.title("🇰🇷 Panel Kontrol")
    # Mode Konverter Angka telah dihapus
    mode = st.radio("Pilih Mode:", ["Belajar & Tanya", "Roleplay Percakapan", "Kuis Berjenjang"])
    
    st.write("---")
    if st.button("+ Chat Baru", use_container_width=True):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c = conn.cursor()
        c.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", ("Percakapan Baru", now))
        conn.commit()
        st.session_state.current_session_id = c.lastrowid
        if 'curr_q' in st.session_state: del st.session_state.curr_q
        if 'rp_active' in st.session_state: del st.session_state.rp_active
        st.rerun()

    st.write("### Riwayat Belajar")
    c = conn.cursor()
    c.execute("SELECT id, title FROM sessions ORDER BY id DESC")
    sessions_list = c.fetchall()
    
    for s_id, s_title in sessions_list:
        col_chat, col_del = st.columns([4, 1])
        with col_chat:
            if st.button(f"📄 {s_title}", key=f"s_{s_id}", use_container_width=True):
                st.session_state.current_session_id = s_id
                if 'curr_q' in st.session_state: del st.session_state.curr_q
                st.rerun()
        with col_del:
            if st.button("🗑️", key=f"del_{s_id}"):
                c.execute("DELETE FROM sessions WHERE id = ?", (s_id,))
                c.execute("DELETE FROM messages WHERE session_id = ?", (s_id,))
                conn.commit()
                st.rerun()

if "current_session_id" not in st.session_state:
    if sessions_list: st.session_state.current_session_id = sessions_list[0][0]
    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        c = conn.cursor()
        c.execute("INSERT INTO sessions (title, created_at) VALUES (?, ?)", ("Percakapan Baru", now))
        conn.commit()
        st.session_state.current_session_id = c.lastrowid

# --- 6. TAMPILAN UTAMA ---

if mode == "Belajar & Tanya":
    st.title("🎓 Mode Belajar")
    c = conn.cursor()
    c.execute("SELECT id, role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (st.session_state.current_session_id,))
    msgs = c.fetchall()

    for m_id, role, content in msgs:
        with st.chat_message(role):
            st.markdown(content)
            if role == "assistant" and "[" in content:
                variants = re.findall(r"\[(.*?)\]", content)
                for i, v in enumerate(variants):
                    parts = v.split("|")
                    if len(parts) >= 3:
                        ko, ro, idn = parts[0].strip(), parts[1].strip(), parts[2].strip()
                        col_a, col_b = st.columns([1, 6])
                        with col_a:
                            if st.button(f"🔊 Play", key=f"aud_{m_id}_{i}"):
                                audio = play_audio(ko)
                                if audio: st.audio(audio, format="audio/mp3", autoplay=True)
                        with col_b:
                            st.caption(f"**{ko}** ({ro}): {idn}")

    if prompt := st.chat_input("Tanya guru..."):
        st.chat_message("user").markdown(prompt)
        
        # UPDATE JUDUL: Ganti judul sesi jika ini pesan pertama
        if len(msgs) == 0:
            new_title = prompt[:25] + "..." if len(prompt) > 25 else prompt
            c.execute("UPDATE sessions SET title = ? WHERE id = ?", (new_title, st.session_state.current_session_id))
        
        c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, 'user', ?)", (st.session_state.current_session_id, prompt))
        conn.commit()
        
        instruction = "Kamu Guru Korea. Beri [Korea | Romaji | Indo] untuk tiap kata kunci."
        resp = model.generate_content(f"{instruction}\nSiswa: {prompt}")
        
        c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, 'assistant', ?)", (st.session_state.current_session_id, resp.text))
        conn.commit()
        st.rerun()

elif mode == "Roleplay Percakapan":
    st.title("🎭 Simulator Roleplay")
    st.info("AI akan menjadi lawan bicaramu. Berlatihlah menggunakan tingkatan bahasa yang sesuai!")

    col1, col2 = st.columns(2)
    with col1:
        skenario = st.selectbox("Situasi:", ["Bertemu Guru", "Membeli Tiket", "Kenalan di Kafe", "Wawancara Kerja", "Tersesat"])
    with col2:
        custom = st.text_input("Skenario Lain:", placeholder="Contoh: Belanja di pasar...")

    situasi_final = custom if custom else skenario

    if st.button("Mulai Roleplay 🎬", use_container_width=True):
        st.session_state.roleplay_active = True
        sys_p = (f"Skenario: {situasi_final}. Kamu lawan bicara (Orang Kedua). Gunakan [Hangul | Romaji | Arti].")
        st.session_state.rp_messages = [{"role": "system", "content": sys_p}]
        
        with st.spinner("Karakter sedang bersiap..."):
            res = model.generate_content(sys_p + " Mulailah percakapan!")
            st.session_state.rp_messages.append({"role": "assistant", "content": res.text})

    if st.session_state.get("roleplay_active"):
        for m in st.session_state.rp_messages:
            if m["role"] != "system":
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])
                    if m["role"] == "assistant":
                        match = re.search(r"\[(.*?)\|", m["content"])
                        if match and st.button("🔊 Play", key=f"rp_aud_{hash(m['content'])}"):
                            audio = play_audio(match.group(1))
                            if audio: st.audio(audio, format="audio/mp3", autoplay=True)

        if rp_in := st.chat_input("Balas karakter ini..."):
            st.session_state.rp_messages.append({"role": "user", "content": rp_in})
            full_h = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.rp_messages])
            response = model.generate_content(full_h)
            st.session_state.rp_messages.append({"role": "assistant", "content": response.text})
            st.rerun()

    if st.button("Reset Roleplay 🔄"):
        if "roleplay_active" in st.session_state:
            del st.session_state.roleplay_active
            del st.session_state.rp_messages
            st.rerun()

elif mode == "Kuis Berjenjang":
    if 'q_level' not in st.session_state: st.session_state.q_level = "Mudah"
    if 'q_step' not in st.session_state: st.session_state.q_step = 1
    if 'q_score' not in st.session_state: st.session_state.q_score = 0
    if 'q_done' not in st.session_state: st.session_state.q_done = False
    levels = ["Mudah", "Sedang", "Susah", "Profesional"]

    c1, c2, c3 = st.columns([3, 2, 1])
    with c1: st.title("🏆 Kuis Pro")
    with c2: 
        lv = st.selectbox("Level:", levels, index=levels.index(st.session_state.q_level))
        if lv != st.session_state.q_level:
            st.session_state.q_level = lv; st.session_state.q_step = 1; st.session_state.q_score = 0
            if 'curr_q' in st.session_state: del st.session_state.curr_q
            st.rerun()
    with c3:
        if st.button("Reset 🔄"):
            st.session_state.q_level="Mudah"; st.session_state.q_score=0; st.session_state.q_step=1; st.session_state.q_done=False
            if 'curr_q' in st.session_state: del st.session_state.curr_q
            st.rerun()

    if st.session_state.q_done:
        st.success(f"### Level {st.session_state.q_level} Selesai! Skor: {st.session_state.q_score}/100")
        if st.button("Ulang / Lanjut"):
            st.session_state.q_step = 1; st.session_state.q_score = 0; st.session_state.q_done = False
            if 'curr_q' in st.session_state: del st.session_state.curr_q
            st.rerun()
        st.stop()

    c = conn.cursor()
    c.execute("SELECT content FROM messages WHERE session_id = ? AND role='assistant' AND content LIKE '%|%'", (st.session_state.current_session_id,))
    history_raw = c.fetchall()
    context = "\n".join([r[0] for r in history_raw])

    if 'curr_q' not in st.session_state:
        with st.spinner("Menyiapkan soal..."):
            src = f"Gunakan riwayat ini: {context}" if history_raw else "Gunakan kosakata umum"
            p_q = f"{src}\nBuat 1 soal kuis Korea {st.session_state.q_level}. Format JSON: {{\"q\": \"soal\", \"r\": \"baca\", \"a\": \"benar\", \"o\": [\"salah1\", \"salah2\", \"salah3\"]}}"
            try:
                res = model.generate_content(p_q)
                data = json.loads(re.search(r'\{.*\}', res.text, re.DOTALL).group())
                opts = data['o'] + [data['a']]; random.shuffle(opts)
                st.session_state.curr_q = {"q":data['q'], "r":data['r'], "a":data['a'], "opts":opts}
            except: st.error("Gagal memuat soal!"); st.stop()

    st.write(f"**Soal {st.session_state.q_step} / 5**")
    st.progress(st.session_state.q_step / 5)
    q = st.session_state.curr_q
    st.subheader(q['q'])
    st.caption(f"Baca: {q['r']}")
    ans = st.radio("Pilih jawaban:", q['opts'], index=None, key=f"q_{st.session_state.q_step}")
    if st.button("Kirim Jawaban"):
        if ans == q['a']:
            st.success("Benar!"); st.session_state.q_score += 20
        else: st.error(f"Salah! Jawaban: {q['a']}")
        if st.session_state.q_step < 5:
            st.session_state.q_step += 1; del st.session_state.curr_q; st.rerun()
        else: st.session_state.q_done = True; st.rerun()
