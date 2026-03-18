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
    st.title("🎭 Simulator Percakapan Interaktif")
    st.info("AI akan menjadi lawan bicaramu. Berlatihlah menggunakan tingkatan bahasa yang sesuai!")

    # 1. Pilihan Skenario & Peran
    col1, col2 = st.columns(2)
    with col1:
        skenario = st.selectbox("Pilih Situasi:", [
            "Bertemu Guru di Taman", 
            "Membeli Tiket Konser di Loket", 
            "Bertemu Teman Lama di Kafe",
            "Wawancara Kerja di Perusahaan IT",
            "Tersesat dan Tanya Polisi"
        ])
    with col2:
        custom_skenario = st.text_input("Atau buat skenario sendiri:", placeholder="Contoh: Debat dengan kasir supermarket...")

    situasi_final = custom_skenario if custom_skenario else skenario

    # 2. Tombol Mulai
    if st.button("Mulai Percakapan 🎬", use_container_width=True):
        st.session_state.roleplay_active = True
        # Prompt sistem untuk mengatur identitas AI dan User
        system_prompt = (
            f"Skenario: {situasi_final}. "
            "Aturan: Kamu (AI) adalah ORANG KEDUA dalam cerita ini. Pengguna adalah ORANG PERTAMA (Subjek 'Aku'). "
            "Tugasmu: Bertindaklah sepenuhnya sebagai karakter lawan bicara dalam skenario tersebut. "
            "Gunakan tingkatan bahasa (formal/sopan/banmal) yang logis untuk karaktermu terhadap pengguna. "
            "Berikan respon dalam Bahasa Korea, lalu di bawahnya berikan format [Hangul | Romaji | Arti] "
            "dan tambahkan instruksi pendek dalam kurung ( ) tentang apa yang harus dilakukan pengguna selanjutnya."
        )
        
        # Inisialisasi pesan
        st.session_state.rp_messages = [{"role": "system", "content": system_prompt}]
        
        # AI Memulai Duluan
        with st.spinner("Karakter sedang bersiap..."):
            first_resp = model.generate_content(system_prompt + " Mulailah percakapan sebagai karaktermu.")
            st.session_state.rp_messages.append({"role": "assistant", "content": first_resp.text})

    # 3. Area Chat Roleplay
    if "roleplay_active" in st.session_state:
        st.write("---")
        # Menampilkan percakapan yang sedang berlangsung
        for msg in st.session_state.rp_messages:
            if msg["role"] != "system":
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    
                    # Fitur Audio Otomatis untuk Respon AI
                    if msg["role"] == "assistant":
                        match = re.search(r"\[(.*?)\|", msg["content"])
                        if match:
                            ko_text = match.group(1).strip()
                            if st.button(f"🔊 Dengar Suara Karakter", key=f"rp_aud_{hash(msg['content'])}"):
                                audio = play_audio(ko_text)
                                if audio: st.audio(audio, format="audio/mp3", autoplay=True)

        # Input Balasan dari Pengguna
        if user_input := st.chat_input("Balas karakter ini..."):
            st.session_state.rp_messages.append({"role": "user", "content": user_input})
            
            with st.spinner("Karakter sedang mengetik..."):
                # Kirim seluruh riwayat agar AI ingat konteks
                full_history = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.rp_messages])
                response = model.generate_content(full_history)
                st.session_state.rp_messages.append({"role": "assistant", "content": response.text})
                st.rerun()

    if st.button("Reset Roleplay 🔄"):
        if "roleplay_active" in st.session_state:
            del st.session_state.roleplay_active
            del st.session_state.rp_messages
            st.rerun()


    # --- 3. AMBIL RIWAYAT CHAT ---
    c = conn.cursor()
    c.execute("SELECT content FROM messages WHERE role='assistant' AND content LIKE '%|%' ORDER BY id DESC LIMIT 15")
    history_data = c.fetchall()
    context_bahan = "\n".join([row[0] for row in history_data])

    # --- 4. GENERATE SOAL (DENGAN FALLBACK) ---
    if 'curr_q' not in st.session_state:
        with st.spinner("Menyusun soal..."):
            # Jika history kosong, AI buat soal acak. Jika ada, AI buat dari history.
            source_text = f"Berdasarkan riwayat: {context_bahan}" if len(history_data) >= 2 else "Buat soal kosakata umum"
            
            p = (
                f"{source_text}\n\n"
                f"Buat 1 soal kuis Korea level {st.session_state.q_level}. "
                "Format JSON MURNI: {\"q\": \"soal\", \"r\": \"cara baca\", \"a\": \"jawaban benar\", \"o\": [\"salah1\", \"salah2\", \"salah3\"]}"
            )
            
            try:
                res = model.generate_content(p)
                raw = re.search(r'\{.*\}', res.text, re.DOTALL).group()
                data = json.loads(raw)
                opts = data['o'] + [data['a']]; random.shuffle(opts)
                st.session_state.curr_q = {"q": data['q'], "r": data['r'], "a": data['a'], "opts": opts}
            except Exception as e:
                st.error(f"Gagal memproses soal: {e}")
                st.stop() # Hapus ini jika ingin tetap munculkan tombol refresh

elif mode == "Kuis Berjenjang":
    # --- 1. INISIALISASI STATE (Agar tidak error saat refresh) ---
    if 'q_level' not in st.session_state: st.session_state.q_level = "Mudah"
    if 'q_score' not in st.session_state: st.session_state.q_score = 0
    if 'q_step' not in st.session_state: st.session_state.q_step = 1
    if 'q_done' not in st.session_state: st.session_state.q_done = False
    
    levels = ["Mudah", "Sedang", "Susah", "Profesional"]

    # --- 2. HEADER & NAVIGASI (Atas Kanan) ---
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        st.title("🏆 Kuis Pintar")
    with c2: 
        lv = st.selectbox("Pilih Level:", levels, index=levels.index(st.session_state.q_level))
        if lv != st.session_state.q_level:
            st.session_state.q_level = lv; st.session_state.q_step = 1; st.session_state.q_score = 0
            if 'curr_q' in st.session_state: del st.session_state.curr_q
            st.rerun()
    with c3:
        if st.button("Reset 🔄", use_container_width=True):
            st.session_state.q_level = "Mudah"; st.session_state.q_score = 0; st.session_state.q_step = 1; st.session_state.q_done = False
            if 'curr_q' in st.session_state: del st.session_state.curr_q
            st.rerun()

    st.write("---")

    # --- 3. TAMPILAN SELESAI LEVEL ---
    if st.session_state.q_done:
        st.balloons()
        st.success(f"### 🎉 Level {st.session_state.q_level} Selesai!")
        st.metric("Skor Akhir", f"{st.session_state.q_score} / 100")
        
        col_end1, col_end2 = st.columns(2)
        with col_end1:
            if st.button("Ulang Level Ini 🔄", use_container_width=True):
                st.session_state.q_step = 1; st.session_state.q_score = 0; st.session_state.q_done = False
                if 'curr_q' in st.session_state: del st.session_state.curr_q
                st.rerun()
        with col_end2:
            idx = levels.index(st.session_state.q_level)
            if idx < len(levels) - 1:
                if st.button(f"Lanjut ke Level {levels[idx+1]} ➡️", use_container_width=True):
                    st.session_state.q_level = levels[idx+1]; st.session_state.q_step = 1; st.session_state.q_score = 0; st.session_state.q_done = False
                    if 'curr_q' in st.session_state: del st.session_state.curr_q
                    st.rerun()
            else:
                st.info("Hebat! Kamu sudah mencapai level tertinggi.")
        st.stop()

    # --- 4. LOGIKA PENGAMBILAN BAHAN (History vs General) ---
    c = conn.cursor()
    # Mencari pesan asisten yang berisi format materi [ | | ]
    c.execute("SELECT content FROM messages WHERE role='assistant' AND content LIKE '%|%' ORDER BY id DESC LIMIT 10")
    history_raw = c.fetchall()
    context_bahan = "\n".join([r[0] for r in history_raw])

    # --- 5. GENERATE SOAL (JSON Safe) ---
    if 'curr_q' not in st.session_state:
        with st.spinner("Sedang meracik soal untukmu..."):
            # Jika ada history, gunakan sebagai referensi utama
            if len(history_raw) >= 1:
                source_instr = f"Gunakan riwayat pelajaran ini sebagai referensi utama: {context_bahan}"
                mode_info = "💡 Soal dibuat berdasarkan riwayat chatmu."
            else:
                source_instr = "Buatlah soal kosakata Korea umum yang berguna."
                mode_info = "🌐 Belum ada riwayat chat, menampilkan soal umum."

            st.session_state.q_mode_info = mode_info # Simpan info mode

            prompt = (
                f"{source_instr}\n\n"
                f"Buatlah 1 soal kuis pilihan ganda Level {st.session_state.q_level}.\n"
                "Format JSON MURNI: {\"q\": \"pertanyaan\", \"r\": \"cara baca\", \"a\": \"jawaban benar\", \"o\": [\"salah1\", \"salah2\", \"salah3\"]}"
            )
            
            try:
                res = model.generate_content(prompt)
                raw_json = re.search(r'\{.*\}', res.text, re.DOTALL).group()
                data = json.loads(raw_json)
                
                all_opts = data['o'] + [data['a']]
                random.shuffle(all_opts)
                
                st.session_state.curr_q = {
                    "question": data['q'],
                    "reading": data['r'],
                    "answer": data['a'],
                    "options": all_opts
                }
            except:
                st.error("Gagal memuat soal. Pastikan koneksi stabil.")
                if st.button("Refresh Soal"): st.rerun()
                st.stop()

    # --- 6. TAMPILAN PERTANYAAN ---
    st.info(st.session_state.q_mode_info) # Tampilkan info sumber soal
    st.write(f"**Soal {st.session_state.q_step} / 5**")
    st.progress(st.session_state.q_step / 5)
    
    q_data = st.session_state.curr_q
    st.subheader(q_data['question'])
    st.caption(f"Cara baca: {q_data['reading']}")
    
    pilihan = st.radio("Pilih jawaban yang paling tepat:", q_data['options'], index=None)

    if st.button("Kirim Jawaban", use_container_width=True):
        if not pilihan:
            st.warning("Pilih salah satu jawaban dulu ya!")
        else:
            if pilihan == q_data['answer']:
                st.success("✨ Benar! +20 Poin")
                st.session_state.q_score += 20
            else:
                st.error(f"❌ Salah. Jawaban yang benar adalah: {q_data['answer']}")
            
            # Berpindah soal atau selesai
            if st.session_state.q_step < 5:
                st.session_state.q_step += 1
                del st.session_state.curr_q
                st.rerun()
            else:
                st.session_state.q_done = True
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
