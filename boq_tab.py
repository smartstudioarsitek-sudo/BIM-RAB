import streamlit as st
import pandas as pd
import google.generativeai as genai
import json

# ==========================================
# 1. ENGINE AI (VALIDATOR SNI & PERMEN PUPR)
# ==========================================
def get_best_model(api_key):
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        priority = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-1.0-pro']
        selected = next((m for m in priority if m in models), models[0] if models else None)
        return (genai.GenerativeModel(selected), selected) if selected else (None, None)
    except Exception as e:
        return None, str(e)

def build_system_context(data_proyek):
    """Mengubah Data RAB menjadi Narasi untuk AI"""
    json_data = json.dumps(data_proyek, indent=2)
    return f"""
    ROLE: Anda adalah Ahli Teknik Sipil & Quantity Surveyor (QS) Senior untuk Dinas PUPR.
    TUGAS: Memvalidasi Back-Up Data Volume (BoQ) agar sesuai standar teknis Indonesia (SNI).
    
    DATA RAB PROYEK (JSON):
    {json_data}

    ATURAN VALIDASI:
    1. Ratio Besi: Saluran/Box normalnya 100-150 kg/m3. Jika >200 kg/m3 peringatkan "Boros".
    2. Galian: Volume Galian biasanya 1.2x - 1.5x Volume Struktur (karena ada kemiringan & ruang kerja).
    3. Bekisting: Luas sisi vertikal beton basah.
    
    Jawablah pertanyaan user dengan tegas, teknis, dan mengacu pada data di atas.
    """

# ==========================================
# 2. MODUL SKETSA TEKNIS (VISUALISASI)
# ==========================================
def get_sketch_uditch(b, h, t_cm):
    scale = 100; t_vis = max(10, t_cm * 2)
    w_out = (b*scale) + (2*t_vis); h_out = (h*scale) + t_vis
    # Gambar U-Ditch (Terbuka Atas) + Tanah Galian (Garis Putus-putus)
    return f"""
    <svg width="220" height="180" viewBox="-30 -30 {w_out+60} {h_out+60}" xmlns="http://www.w3.org/2000/svg" style="background:white;">
        <path d="M-20,-10 L-10,{h_out+10} L{w_out+10},{h_out+10} L{w_out+20},-10" fill="none" stroke="#7f8c8d" stroke-dasharray="5,5" stroke-width="1"/>
        <text x="-25" y="{h_out/2}" font-size="10" fill="#7f8c8d" transform="rotate(-90, -25, {h_out/2})">Galian</text>
        <path d="M0,0 L0,{h_out} L{w_out},{h_out} L{w_out},0 L{w_out-t_vis},0 L{w_out-t_vis},{(h*scale)} L{t_vis},{(h*scale)} L{t_vis},0 Z" fill="#bdc3c7" stroke="black" stroke-width="2"/>
        <text x="{w_out/2}" y="{(h*scale)/2}" fill="red" font-weight="bold" text-anchor="middle">B={b}m</text>
        <text x="-10" y="{h_out/2}" fill="blue" transform="rotate(-90, -10, {h_out/2})" text-anchor="middle">H={h}m</text>
    </svg>"""

def get_sketch_box(w, h, t_cm):
    return f"""<svg width="200" height="150" viewBox="0 0 200 150" xmlns="http://www.w3.org/2000/svg" style="background:white;"><rect x="10" y="10" width="180" height="130" fill="#95a5a6" stroke="black"/><rect x="30" y="30" width="140" height="90" fill="white" stroke="black"/><text x="100" y="80" text-anchor="middle" font-weight="bold">BOX {w}x{h}</text></svg>"""

def get_sketch_trapezoid(b, h, m):
    return f"""<svg width="200" height="150" viewBox="0 0 200 150" xmlns="http://www.w3.org/2000/svg" style="background:white;"><polygon points="20,20 180,20 140,130 60,130" fill="#81ecec" fill-opacity="0.5" stroke="black"/><text x="100" y="15" text-anchor="middle">Lebar Atas</text><text x="100" y="145" text-anchor="middle">B={b}m</text></svg>"""

# ==========================================
# 3. LOGIKA BREAKDOWN ITEM (MESIN HITUNG)
# ==========================================
def generate_breakdown(item):
    """Memecah 1 Item menjadi Sub-Item Pekerjaan (Galian, Beton, Besi, dll)"""
    vol = item['vol']
    dim = item.get('dimensi', {})
    tipe = item['tipe']
    panjang = dim.get('panjang', 1)
    
    breakdown = []
    
    # 1. PEKERJAAN PERSIAPAN & TANAH
    if vol.get('vol_bongkaran', 0) > 0:
        breakdown.append({
            "kode": "T.15.a", "uraian": "Bongkaran Pasangan Eksisting",
            "rumus": f"Volume Beton Lama (Asumsi sama dengan baru)",
            "hitung": f"{vol['vol_bongkaran']:.3f} m3"
        })
        
    if vol.get('vol_galian', 0) > 0:
        # Reverse logic untuk penjelasan
        luas_galian = vol['vol_galian'] / panjang if panjang > 0 else 0
        breakdown.append({
            "kode": "T.06.a.1", "uraian": "Galian Tanah Biasa",
            "rumus": "Luas Penampang Galian (Profil + Space Kerja) x Panjang",
            "hitung": f"{luas_galian:.3f} m2 x {panjang} m = <b>{vol['vol_galian']:.3f} m3</b>"
        })
        
    if vol.get('vol_timbunan', 0) > 0:
        breakdown.append({
            "kode": "T.14.a", "uraian": "Timbunan Kembali Dipadatkan",
            "rumus": "(Vol. Galian - Vol. Struktur) x Faktor Pemadatan",
            "hitung": f"({vol['vol_galian']:.2f} - {vol.get('vol_beton',0):.2f}) x 0.45 = <b>{vol['vol_timbunan']:.3f} m3</b>"
        })

    # 2. PEKERJAAN STRUKTUR
    if vol.get('vol_beton', 0) > 0:
        desc = "Volume Profil x Panjang"
        if "Saluran Beton" in tipe:
            b, h, t = dim.get('b',0), dim.get('h',0), dim.get('t_cm',0)/100
            luas_beton = ((b + 2*t)*(h + t)) - (b*h)
            desc = f"((L.Luar - L.Dalam) x P) = ({luas_beton:.3f} m2 x {panjang} m)"
            
        breakdown.append({
            "kode": "B.05.a", "uraian": "Beton Mutu K-225",
            "rumus": desc,
            "hitung": f"<b>{vol['vol_beton']:.3f} m3</b>"
        })
    
    if vol.get('vol_batu', 0) > 0:
        breakdown.append({
            "kode": "P.01.a", "uraian": "Pasangan Batu Kali 1:4",
            "rumus": "Luas Penampang Basah x Panjang",
            "hitung": f"<b>{vol['vol_batu']:.3f} m3</b>"
        })

    # 3. PEKERJAAN PENDUKUNG
    if vol.get('berat_besi', 0) > 0:
        # Hitung Ratio
        ratio = vol['berat_besi'] / vol['vol_beton'] if vol['vol_beton'] > 0 else 0
        breakdown.append({
            "kode": "B.17.a", "uraian": "Pembesian (Polos/Ulir)",
            "rumus": f"Volume Beton x Ratio Besi Rata-rata ({ratio:.1f} kg/m3)",
            "hitung": f"{vol['vol_beton']:.2f} m3 x {ratio:.1f} kg/m3 = <b>{vol['berat_besi']:.2f} kg</b>"
        })
        
    if vol.get('luas_bekisting', 0) > 0:
        breakdown.append({
            "kode": "B.20.a", "uraian": "Pasang Bekisting",
            "rumus": "Luas Bidang Sentuh Beton x Panjang",
            "hitung": f"<b>{vol['luas_bekisting']:.3f} m2</b>"
        })

    if vol.get('luas_plester', 0) > 0:
        breakdown.append({
            "kode": "P.04.e", "uraian": "Plesteran 1:3 + Acian",
            "hitung": f"<b>{vol['luas_plester']:.3f} m2</b>"
        })

    return breakdown

# ==========================================
# 4. TAB RENDERER (UI UTAMA)
# ==========================================
def render_boq_tab(data_proyek):
    # Setup AI
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        api_key = st.text_input("🔑 Masukkan Google API Key (Wajib untuk Validasi):", type="password")
    
    model_ai = None
    if api_key:
        model_ai, _ = get_best_model(api_key)

    # --- CHATBOT SECTION ---
    st.markdown("### 🤖 Asisten Validasi RAB (Tukang Hitung)")
    st.info("AI siap menjelaskan detail Galian, Besi, dll. Contoh: 'Jelaskan perhitungan galian Saluran 1', 'Apakah ratio besi Saluran 2 wajar?'")
    
    if "messages" not in st.session_state: st.session_state.messages = []
    for msg in st.session_state.messages: st.chat_message(msg["role"]).write(msg["content"])
    
    if prompt := st.chat_input("Tanya validasi perhitungan..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        if model_ai and data_proyek:
            with st.spinner("Menghitung ulang..."):
                ctx = build_system_context(data_proyek)
                res = model_ai.generate_content(f"{ctx}\nUSER: {prompt}")
                st.chat_message("assistant").write(res.text)
                st.session_state.messages.append({"role": "assistant", "content": res.text})
        else:
            st.error("Butuh API Key & Data Proyek.")

    st.markdown("---")
    
    # --- REPORT SECTION ---
    st.header("📑 Laporan Back-Up Data Volume (Lengkap)")
    st.caption("Mencakup: Galian, Timbunan, Beton, Besi, Bekisting, Bongkaran")

    # CSS Print Friendly
    st.markdown("""<style>
    @media print { 
        .stChatInput, [data-testid="stSidebar"], .stChatMessage, header, footer, .no-print {display: none !important;} 
        .boq-card {break-inside: avoid; border: 1px solid #000; margin-bottom: 20px; page-break-after: auto;}
        .boq-table th {background: #ccc !important; color: black !important;}
    }
    .boq-table {width:100%; border-collapse: collapse; font-size: 0.9rem;}
    .boq-table th, .boq-table td {border: 1px solid #ddd; padding: 6px;}
    .boq-table th {background-color: #2c3e50; color: white;}
    .boq-header {background: #2980b9; color: white; padding: 10px; font-weight: bold; border-radius: 5px 5px 0 0;}
    </style>""", unsafe_allow_html=True)

    if not data_proyek:
        st.warning("Data Kosong. Input dulu di Tab 1.")
        return

    for idx, item in enumerate(data_proyek):
        dim = item.get('dimensi', {})
        tipe = item['tipe']
        
        # 1. Pilih Sketsa
        sketch = ""
        if "Saluran Beton" in tipe: sketch = get_sketch_uditch(dim.get('b',0), dim.get('h',0), dim.get('t_cm',0))
        elif "Gorong" in tipe: sketch = get_sketch_box(dim.get('w',0), dim.get('h',0), dim.get('t_cm',0))
        elif "Saluran Batu" in tipe: sketch = get_sketch_trapezoid(dim.get('l_bawah',0), dim.get('h',0), 0)
        
        # 2. Generate Tabel Breakdown
        rows = generate_breakdown(item)
        table_html = """
        <table class="boq-table">
            <thead><tr><th width="15%">Kode</th><th width="35%">Uraian Pekerjaan</th><th width="30%">Rumus / Logika</th><th width="20%">Volume Hitung</th></tr></thead>
            <tbody>
        """
        for r in rows:
            table_html += f"<tr><td>{r['kode']}</td><td>{r['uraian']}</td><td><small>{r['rumus']}</small></td><td>{r['hitung']}</td></tr>"
        table_html += "</tbody></table>"

        # 3. Render Card
        st.markdown(f"""
        <div class="boq-card" style="border:1px solid #ddd; border-radius:5px; margin-bottom:30px; background:white; color:black;">
            <div class="boq-header">#{idx+1}. {item['nama']} <span style="font-weight:normal; font-size:0.8em">({tipe})</span></div>
            <div style="display:flex; flex-wrap:wrap; padding:15px;">
                <div style="flex: 0 0 230px; text-align:center; padding-right:15px; border-right:1px dashed #ccc; margin-bottom:10px;">
                    {sketch}<br><small><i>Sketsa Penampang & Galian</i></small>
                </div>
                <div style="flex:1; padding-left:15px; min-width:300px;">
                    {table_html}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
