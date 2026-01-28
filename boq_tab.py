import streamlit as st
import pandas as pd
import google.generativeai as genai
import json

# ==========================================
# 1. ENGINE AI & CONTEXT LOADER
# ==========================================
def get_best_model(api_key):
    """Mendeteksi Model Terbaik (Flash/Pro)"""
    try:
        genai.configure(api_key=api_key)
        # Coba listing model
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Prioritas: Flash (Cepat) -> Pro (Pintar)
        priority = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-1.0-pro']
        selected = next((m for m in priority if m in models), None)
        
        if not selected and models: selected = models[0] # Fallback
        
        if selected: return genai.GenerativeModel(selected), selected
        return None, "Tidak ada model aktif."
    except Exception as e:
        return None, str(e)

def build_system_context(data_proyek):
    """
    Fungsi ini mengubah Data Proyek + Logika Aplikasi menjadi 'Ingatan' AI.
    Sehingga AI tahu apa yang sedang dikerjakan User.
    """
    json_data = json.dumps(data_proyek, indent=2)
    
    context = f"""
    ROLE: 
    Kamu adalah Senior Quantity Surveyor (QS) & Ahli Teknik Sipil untuk aplikasi "Pro QS V.12".
    Tugasmu adalah membantu user memvalidasi, menghitung, dan menjelaskan RAB/BoQ.

    DATA PROYEK SAAT INI (JSON):
    {json_data}

    DASAR PENGETAHUAN APLIKASI:
    1. Standar: Mengacu pada Permen PUPR No. 1 Tahun 2022 / No. 182 Tahun 2025 (SDA).
    2. Rumus Saluran Beton (U-Ditch): Volume = (Luas Penampang Luar - Luas Dalam) x Panjang.
    3. Rumus Saluran Batu: Volume = ((Lebar Atas + Bawah)/2) x Tinggi x Panjang.
    4. Rumus Besi: Berat = Volume Beton x Ratio Besi (kg/m3). 
    5. Validasi:
       - Ratio besi normal saluran: 100-150 kg/m3. Jika > 200 kg/m3 anggap pemborosan.
       - Tebal beton minimal U-Ditch biasanya 10-15 cm.
    
    INSTRUKSI MENJAWAB:
    - Jawab pertanyaan user berdasarkan DATA PROYEK di atas.
    - Jika user tanya "Apakah Saluran 1 boros?", cek 'rho_data' atau hitung ratio besi dari data json.
    - Jika user tanya rumus, jelaskan logika geometrinya.
    - Gunakan Bahasa Indonesia yang profesional namun luwes (seperti konsultan ke klien).
    - Jika data tidak ada di JSON, katakan jujur.
    """
    return context

# ==========================================
# 2. MODUL SKETSA (TETAP DIPERTAHANKAN)
# ==========================================
def get_sketch_uditch(b, h, t_cm):
    """Sketsa U-Ditch SVG"""
    scale = 100; t_vis = max(10, t_cm * 2)
    w = b * scale if b > 0 else 50; h_inner = h * scale if h > 0 else 50
    w_out = w + 2*t_vis; h_out = h_inner + t_vis
    return f"""<svg width="200" height="150" viewBox="0 0 {w_out+40} {h_out+40}" xmlns="http://www.w3.org/2000/svg" style="background:white;"><path d="M0,0 L{w_out},0 L{w_out},{h_out} L{w_out-t_vis},{h_out} L{w_out-t_vis},{t_vis} L{t_vis},{t_vis} L{t_vis},{h_out} L0,{h_out} Z" fill="#bdc3c7" stroke="black" transform="translate(20,20)"/><text x="{20+w_out/2}" y="15" fill="red" text-anchor="middle">B={b}m</text><text x="5" y="{20+h_out/2}" fill="red" transform="rotate(-90,5,{20+h_out/2})" text-anchor="middle">H={h}m</text></svg>"""

def get_sketch_trapezoid(b, h, m, t_cm):
    """Sketsa Trapesium SVG"""
    scale = 80; w_top = (b*scale) + (2*m*h*scale)
    return f"""<svg width="250" height="150" viewBox="-20 -20 {w_top+40} {h*scale+50}" xmlns="http://www.w3.org/2000/svg" style="background:white;"><polygon points="0,0 {w_top},0 {(b*scale)+(m*h*scale)},{h*scale} {m*h*scale},{h*scale}" fill="#95a5a6" fill-opacity="0.5" stroke="black"/><text x="{w_top/2}" y="-5" fill="red" text-anchor="middle">L.Atas</text><text x="{w_top/2}" y="{h*scale+15}" fill="red" text-anchor="middle">B={b}m</text></svg>"""

# ==========================================
# 3. TAB UTAMA
# ==========================================
def render_boq_tab(data_proyek):
    
    # --- A. SETUP AI ---
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        api_key = st.text_input("🔑 Masukkan Google API Key:", type="password")
    
    model_ai = None
    if api_key:
        model_ai, model_name = get_best_model(api_key)

    # --- B. UI CHATBOT CONSULTANT (FITUR BARU) ---
    st.markdown("### 🤖 Super QS Assistant")
    st.info("Tanyakan apa saja! Contoh: 'Cek apakah Saluran 1 boros besi?', 'Apa rumus volume galian?', 'Validasi dimensi Saluran 2'")

    # Inisialisasi Chat History
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Tampilkan Chat Terdahulu
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input User
    if prompt := st.chat_input("Ketik pertanyaan teknis Anda di sini..."):
        # 1. Simpan pesan user
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Proses AI
        if model_ai and data_proyek:
            try:
                # KONTEKS INJEKSI: Menggabungkan Data Proyek + Pertanyaan User
                system_instruction = build_system_context(data_proyek)
                full_prompt = f"{system_instruction}\n\nUSER QUESTION: {prompt}"
                
                with st.chat_message("assistant"):
                    with st.spinner("Sedang menganalisa data proyek..."):
                        response = model_ai.generate_content(full_prompt)
                        st.markdown(response.text)
                        # Simpan jawaban AI
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error(f"Error AI: {e}")
        else:
            st.warning("Mohon input Data Proyek dulu atau Masukkan API Key.")

    st.markdown("---")
    
    # --- C. LAPORAN TERSTRUKTUR & SKETSA (BAGIAN BAWAH) ---
    st.header("📑 Laporan Back-Up Data (Printable)")
    
    # CSS Print
    st.markdown("""<style>@media print { [data-testid="stSidebar"], .stChatInput, .stChatMessage, header, footer {display: none !important;} .report-card {break-inside: avoid; border: 1px solid #000; margin-bottom: 20px;} }</style>""", unsafe_allow_html=True)

    if not data_proyek:
        st.warning("Belum ada data input.")
        return

    for idx, item in enumerate(data_proyek):
        # Generate Simple Math Text
        dim = item.get('dimensi', {})
        tipe = item['tipe']
        vol = item['vol']
        steps = []
        sketch = ""

        if "Saluran Beton" in tipe:
            b, h = dim.get('b',0), dim.get('h',0); t = dim.get('t_cm',0)/100
            sketch = get_sketch_uditch(b, h, dim.get('t_cm',0))
            steps = [
                f"<b>1. Luas Penampang:</b> (Luas Luar) - (Luas Dalam)",
                f"= ({(b+2*t):.2f} x {(h+t):.2f}) - ({b} x {h}) = <b>{((b+2*t)*(h+t) - b*h):.3f} m2</b>",
                f"<b>2. Volume Beton:</b> Luas x Panjang ({dim.get('panjang',0)} m)",
                f"= <b>{vol['vol_beton']:.3f} m3</b>"
            ]
        elif "Saluran Batu" in tipe:
            sketch = get_sketch_trapezoid(dim.get('l_bawah',0), dim.get('h',0), 0, 0)
            steps = [f"Volume Batu = Luas Trapesium x Panjang = <b>{vol['vol_batu']:.3f} m3</b>"]
        
        # Render HTML Card
        math_html = "".join([f"<div style='font-family:monospace; margin:5px 0;'>{s}</div>" for s in steps])
        st.markdown(f"""
        <div class="report-card" style="border:1px solid #ddd; padding:15px; border-radius:5px; background:white; color:black;">
            <div style="background:#2c3e50; color:white; padding:5px 10px; font-weight:bold;">#{idx+1}. {item['nama']} ({tipe})</div>
            <div style="display:flex; margin-top:10px;">
                <div style="width:40%; text-align:center; border-right:1px dashed #ccc;">{sketch}<br><small>Sketsa Visual</small></div>
                <div style="width:60%; padding-left:15px;">{math_html}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
