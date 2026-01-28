import streamlit as st
import pandas as pd
import google.generativeai as genai
import json

# ==========================================
# 1. ENGINE AI (VALIDATOR STANDAR PUPR)
# ==========================================
def get_best_model(api_key):
    """Koneksi ke Google Gemini AI"""
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-1.0-pro']
        selected = next((m for m in priority if m in models), models[0] if models else None)
        return (genai.GenerativeModel(selected), selected) if selected else (None, None)
    except Exception as e:
        return None, str(e)

def build_system_context(data_proyek):
    """Mengirim Data ke AI untuk Validasi"""
    json_data = json.dumps(data_proyek, indent=2)
    return f"""
    ROLE: Ahli Quantity Surveyor (QS) & Estimator Proyek Sipil.
    STANDAR: Permen PUPR No. 1 Tahun 2022 / No. 182 Tahun 2025.
    TUGAS: Validasi perhitungan volume back-up data (BoQ).
    
    DATA PROYEK (JSON):
    {json_data}
    
    INSTRUKSI:
    1. Validasi apakah koefisien galian dan timbunan masuk akal.
    2. Cek rasio pembesian (kg/m3).
    3. Jawab pertanyaan user dengan bahasa teknis yang sopan.
    """

# ==========================================
# 2. LOGIKA PERHITUNGAN (BREAKDOWN ITEM)
# ==========================================
def generate_breakdown(item):
    """
    Memecah 1 Item Pekerjaan menjadi Sub-Item Analisa 
    Sesuai Struktur AHSP (Galian, Timbunan, Struktur, Finishing)
    """
    vol = item['vol']
    dim = item.get('dimensi', {})
    tipe = item['tipe']
    panjang = dim.get('panjang', 1)
    
    breakdown = []
    
    # A. PEKERJAAN PERSIAPAN / BONGKARAN
    if vol.get('vol_bongkaran', 0) > 0:
        breakdown.append({
            "kode": "T.15.a", 
            "uraian": "Bongkaran Pasangan Eksisting",
            "rumus": "V = Volume Struktur Lama (Asumsi sama dengan baru)",
            "volume": f"{vol['vol_bongkaran']:.3f}",
            "satuan": "m3"
        })
        
    # B. PEKERJAAN TANAH
    if vol.get('vol_galian', 0) > 0:
        luas_galian = vol['vol_galian'] / panjang if panjang > 0 else 0
        breakdown.append({
            "kode": "T.06.a.1", 
            "uraian": "Galian Tanah Biasa",
            "rumus": f"V = Luas Penampang Galian ({luas_galian:.2f} m2) x Panjang",
            "volume": f"{vol['vol_galian']:.3f}",
            "satuan": "m3"
        })
        
    if vol.get('vol_timbunan', 0) > 0:
        breakdown.append({
            "kode": "T.14.a", 
            "uraian": "Timbunan Kembali Dipadatkan",
            "rumus": "V = (Vol. Galian - Vol. Struktur) x 0.45 (Faktor Gembur)",
            "volume": f"{vol['vol_timbunan']:.3f}",
            "satuan": "m3"
        })

    # C. PEKERJAAN STRUKTUR BETON/BATU
    if vol.get('vol_beton', 0) > 0:
        ket_rumus = "V = Luas Penampang x Panjang"
        if "Saluran Beton" in tipe:
            b, h, t = dim.get('b',0), dim.get('h',0), dim.get('t_cm',0)
            ket_rumus = f"V = ((L.Luar - L.Dalam) x Panjang) | Dimensi: {b}x{h} t={t}cm"
            
        breakdown.append({
            "kode": "B.05.a", 
            "uraian": "Beton Mutu K-225 (Struktur)",
            "rumus": ket_rumus,
            "volume": f"{vol['vol_beton']:.3f}",
            "satuan": "m3"
        })
    
    if vol.get('vol_batu', 0) > 0:
        breakdown.append({
            "kode": "P.01.a", 
            "uraian": "Pasangan Batu Kali Camp. 1:4",
            "rumus": "V = Luas Penampang Trapesium x Panjang",
            "volume": f"{vol['vol_batu']:.3f}",
            "satuan": "m3"
        })

    # D. PEKERJAAN BESI & BEKISTING
    if vol.get('berat_besi', 0) > 0:
        ratio = vol['berat_besi'] / vol['vol_beton'] if vol['vol_beton'] > 0 else 0
        breakdown.append({
            "kode": "B.17.a", 
            "uraian": "Pembesian (Polos/Ulir)",
            "rumus": f"Berat = Vol. Beton x Ratio Besi ({ratio:.1f} kg/m3)",
            "volume": f"{vol['berat_besi']:.2f}",
            "satuan": "kg"
        })
        
    if vol.get('luas_bekisting', 0) > 0:
        breakdown.append({
            "kode": "B.20.a", 
            "uraian": "Pasang Bekisting (2x Pakai)",
            "rumus": "Luas = Keliling Sisi Vertikal Beton x Panjang",
            "volume": f"{vol['luas_bekisting']:.3f}",
            "satuan": "m2"
        })
        
    # E. PEKERJAAN FINISHING (TERJUNAN USBR)
    if vol.get('luas_plester', 0) > 0:
        breakdown.append({
            "kode": "P.04.e", 
            "uraian": "Plesteran 1:3 + Acian",
            "rumus": "Luas = Luas Bidang Basah / Ekspos",
            "volume": f"{vol['luas_plester']:.3f}",
            "satuan": "m2"
        })

    return breakdown

# ==========================================
# 3. TAMPILAN UTAMA (RENDERER)
# ==========================================
def render_boq_tab(data_proyek):
    
    # --- A. SETUP & INPUT KEY ---
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        api_key = st.text_input("🔑 Masukkan Google API Key (Opsional untuk AI):", type="password")
    
    model_ai = None
    if api_key:
        model_ai, _ = get_best_model(api_key)

    # --- B. CHATBOT AI ---
    st.markdown("### 🤖 Asisten Validasi Data")
    st.info("AI dapat membantu mengecek kewajaran volume galian, rasio besi, dll sesuai Permen PUPR.")
    
    if "messages" not in st.session_state: st.session_state.messages = []
    # Tampilkan chat terakhir saja agar bersih
    if st.session_state.messages:
        last_msg = st.session_state.messages[-1]
        st.chat_message(last_msg["role"]).write(last_msg["content"])

    if prompt := st.chat_input("Contoh: 'Cek apakah koefisien galian Saluran 1 sudah benar?'"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        
        if model_ai and data_proyek:
            with st.spinner("Sedang memvalidasi dengan standar PUPR..."):
                ctx = build_system_context(data_proyek)
                res = model_ai.generate_content(f"{ctx}\nUSER QUERY: {prompt}")
                st.chat_message("assistant").write(res.text)
                st.session_state.messages.append({"role": "assistant", "content": res.text})
        else:
            st.warning("Perlu API Key dan Data Proyek untuk menggunakan AI.")

    st.markdown("---")
    
    # --- C. TABEL BACK-UP DATA (FORMAT RESMI) ---
    st.header("📑 Laporan Back-Up Data Volume")
    st.caption("Referensi: Permen PUPR No. 182 Tahun 2025 (AHSP Bidang SDA)")

    # CSS Agar Tabel Rapi saat Print (Ctrl+P)
    st.markdown("""
    <style>
    @media print { 
        .stChatInput, [data-testid="stSidebar"], .stChatMessage, header, footer, .no-print {display: none !important;} 
        .boq-container {break-inside: avoid; margin-bottom: 30px; border: 1px solid #000;}
        .boq-header {background-color: #eee !important; color: #000 !important; border-bottom: 1px solid #000;}
        .boq-table th {background-color: #ccc !important; color: #000 !important;}
    }
    .boq-container {border: 1px solid #ddd; border-radius: 5px; margin-bottom: 25px; background: white; color: black; box-shadow: 0 2px 5px rgba(0,0,0,0.05);}
    .boq-header {background-color: #2c3e50; color: white; padding: 12px 15px; font-weight: bold; border-radius: 5px 5px 0 0;}
    .boq-table {width: 100%; border-collapse: collapse; font-family: 'Arial', sans-serif; font-size: 0.9rem;}
    .boq-table th {background-color: #f8f9fa; color: #333; font-weight: bold; text-align: left; padding: 8px 12px; border-bottom: 2px solid #ddd;}
    .boq-table td {padding: 8px 12px; border-bottom: 1px solid #eee; vertical-align: top;}
    .boq-table tr:last-child td {border-bottom: none;}
    </style>
    """, unsafe_allow_html=True)

    if not data_proyek:
        st.warning("Belum ada data. Silakan input di Tab 1.")
        return

    # GENERATE TABEL PER ITEM
    for idx, item in enumerate(data_proyek):
        rows = generate_breakdown(item)
        
        # HTML Table Construction
        table_html = """
        <table class="boq-table">
            <thead>
                <tr>
                    <th width="10%">Kode</th>
                    <th width="35%">Uraian Pekerjaan</th>
                    <th width="35%">Perhitungan / Rumus</th>
                    <th width="10%">Volume</th>
                    <th width="10%">Satuan</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for r in rows:
            table_html += f"""
            <tr>
                <td>{r['kode']}</td>
                <td>{r['uraian']}</td>
                <td style="font-family:'Consolas', monospace; color:#555;">{r['rumus']}</td>
                <td style="font-weight:bold;">{r['volume']}</td>
                <td>{r['satuan']}</td>
            </tr>
            """
        table_html += "</tbody></table>"
        
        # Render Container
        st.markdown(f"""
        <div class="boq-container">
            <div class="boq-header">
                #{idx+1}. {item['nama']} <span style="font-weight:normal; font-size:0.9em; opacity:0.8;">({item['tipe']})</span>
            </div>
            {table_html}
        </div>
        """, unsafe_allow_html=True)
    
    st.info("💡 Tips: Tekan Ctrl + P untuk mencetak laporan resmi ini.")
