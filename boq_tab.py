import streamlit as st
import pandas as pd
import google.generativeai as genai
import json

# ==========================================
# 1. ENGINE AI (VALIDATOR SNI)
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
    json_data = json.dumps(data_proyek, indent=2)
    return f"""
    ROLE: Ahli Teknik Sipil & QS untuk Dinas PUPR.
    TUGAS: Validasi BoQ.
    DATA: {json_data}
    """

# ==========================================
# 2. MODUL SKETSA "CANTIK" (VERSI FAVORIT ANDA)
# ==========================================
def get_sketch_uditch(b, h, t_cm):
    """Sketsa U-Ditch Bersih & Rapi"""
    scale = 100
    t_vis = max(10, t_cm * 2) 
    
    # Dimensi
    w_inner = b * scale if b > 0 else 50
    h_inner = h * scale if h > 0 else 50
    w_out = w_inner + (2 * t_vis)
    h_out = h_inner + t_vis 
    
    # Path U-Shape
    path_d = f"M0,0 L0,{h_out} L{w_out},{h_out} L{w_out},0 L{w_out-t_vis},0 L{w_out-t_vis},{h_inner} L{t_vis},{h_inner} L{t_vis},0 Z"
    
    return f"""
    <svg width="250" height="200" viewBox="-20 -30 {w_out+40} {h_out+60}" xmlns="http://www.w3.org/2000/svg" style="background:white;">
        <path d="{path_d}" fill="#bdc3c7" stroke="#2c3e50" stroke-width="2" />
        
        <line x1="{t_vis}" y1="{h_inner/2}" x2="{w_out-t_vis}" y2="{h_inner/2}" stroke="#e74c3c" stroke-dasharray="4"/>
        <text x="{w_out/2}" y="{h_inner/2 - 5}" fill="#c0392b" font-family="Arial" font-weight="bold" font-size="14" text-anchor="middle">B = {b} m</text>
        
        <line x1="-10" y1="0" x2="-10" y2="{h_out}" stroke="#2980b9" stroke-width="2"/>
        <text x="-15" y="{h_out/2}" fill="#2980b9" font-family="Arial" font-weight="bold" font-size="14" transform="rotate(-90, -15, {h_out/2})" text-anchor="middle">H = {h} m</text>
        
        <text x="{w_out/2}" y="{h_out + 20}" fill="#333" font-size="12" text-anchor="middle">t = {t_cm} cm</text>
    </svg>
    """

def get_sketch_box(w, h, t_cm):
    """Sketsa Box Culvert Rapi"""
    scale = 100
    t_vis = max(10, t_cm * 2)
    w_out = (w*scale) + 2*t_vis
    h_out = (h*scale) + 2*t_vis
    
    # Path Box (Lubang di tengah)
    path_d = f"M0,0 L0,{h_out} L{w_out},{h_out} L{w_out},0 Z M{t_vis},{t_vis} L{w_out-t_vis},{t_vis} L{w_out-t_vis},{h_out-t_vis} L{t_vis},{h_out-t_vis} Z"
    
    return f"""
    <svg width="250" height="200" viewBox="-20 -20 {w_out+40} {h_out+40}" xmlns="http://www.w3.org/2000/svg" style="background:white;">
        <path d="{path_d}" fill="#95a5a6" fill-rule="evenodd" stroke="#2c3e50" stroke-width="2"/>
        <text x="{w_out/2}" y="{h_out/2}" fill="#c0392b" font-weight="bold" font-size="16" text-anchor="middle">BOX {w}x{h}</text>
    </svg>
    """

def get_sketch_trapezoid(b, h, m):
    """Sketsa Trapesium Rapi"""
    scale = 80
    b_vis = b * scale
    h_vis = h * scale
    m_vis = m * h_vis 
    top_width = b_vis + (2 * m_vis)
    
    return f"""
    <svg width="250" height="200" viewBox="-20 -30 {top_width+40} {h_vis+60}" xmlns="http://www.w3.org/2000/svg" style="background:white;">
        <polygon points="0,0 {top_width},0 {b_vis+m_vis},{h_vis} {m_vis},{h_vis}" fill="#8ecae6" stroke="#2c3e50" stroke-width="2" fill-opacity="0.6" />
        
        <line x1="0" y1="-10" x2="{top_width}" y2="-10" stroke="#e74c3c"/>
        <text x="{top_width/2}" y="-15" fill="#c0392b" text-anchor="middle">Lebar Atas</text>
        <text x="{top_width/2}" y="{h_vis+20}" fill="black" font-weight="bold" text-anchor="middle">B = {b} m</text>
    </svg>
    """

# ==========================================
# 3. LOGIKA HITUNGAN (TETAP LENGKAP)
# ==========================================
def generate_breakdown(item):
    vol = item['vol']
    dim = item.get('dimensi', {})
    tipe = item['tipe']
    panjang = dim.get('panjang', 1)
    
    breakdown = []
    
    # 1. Bongkaran
    if vol.get('vol_bongkaran', 0) > 0:
        breakdown.append({
            "kode": "T.15.a", "uraian": "Bongkaran Pasangan Eksisting",
            "rumus": "Asumsi Vol Bongkaran = Vol Struktur Baru",
            "hitung": f"{vol['vol_bongkaran']:.3f} m3"
        })
        
    # 2. Galian
    if vol.get('vol_galian', 0) > 0:
        luas_g = vol['vol_galian'] / panjang if panjang > 0 else 0
        breakdown.append({
            "kode": "T.06.a.1", "uraian": "Galian Tanah Biasa",
            "rumus": "L.Penampang Galian (Profil + Space) x P",
            "hitung": f"{luas_g:.3f} m2 x {panjang} m = <b>{vol['vol_galian']:.3f} m3</b>"
        })
        
    # 3. Timbunan
    if vol.get('vol_timbunan', 0) > 0:
        breakdown.append({
            "kode": "T.14.a", "uraian": "Timbunan Kembali",
            "rumus": "(Vol.Galian - Vol.Struktur) x 0.45",
            "hitung": f"<b>{vol['vol_timbunan']:.3f} m3</b>"
        })

    # 4. Beton
    if vol.get('vol_beton', 0) > 0:
        desc = "Luas Penampang x Panjang"
        if "Saluran Beton" in tipe:
            b, h, t = dim.get('b',0), dim.get('h',0), dim.get('t_cm',0)/100
            desc = f"((L.Luar - L.Dalam) x P)"
            
        breakdown.append({
            "kode": "B.05.a", "uraian": "Beton Mutu K-225",
            "rumus": desc,
            "hitung": f"<b>{vol['vol_beton']:.3f} m3</b>"
        })
    
    # 5. Batu
    if vol.get('vol_batu', 0) > 0:
        breakdown.append({
            "kode": "P.01.a", "uraian": "Pasangan Batu Kali 1:4",
            "rumus": "Luas Trapesium x Panjang",
            "hitung": f"<b>{vol['vol_batu']:.3f} m3</b>"
        })

    # 6. Besi
    if vol.get('berat_besi', 0) > 0:
        ratio = vol['berat_besi'] / vol['vol_beton'] if vol['vol_beton'] > 0 else 0
        breakdown.append({
            "kode": "B.17.a", "uraian": "Pembesian",
            "rumus": f"Vol Beton x Ratio ({ratio:.0f} kg/m3)",
            "hitung": f"<b>{vol['berat_besi']:.2f} kg</b>"
        })
        
    # 7. Bekisting
    if vol.get('luas_bekisting', 0) > 0:
        breakdown.append({
            "kode": "B.20.a", "uraian": "Pasang Bekisting",
            "rumus": "Luas Sisi Vertikal x Panjang",
            "hitung": f"<b>{vol['luas_bekisting']:.3f} m2</b>"
        })
        
    # 8. Plesteran (USBR)
    if vol.get('luas_plester', 0) > 0:
        breakdown.append({
            "kode": "P.04.e", "uraian": "Plesteran + Acian",
            "rumus": "Luas Bidang Basah",
            "hitung": f"<b>{vol['luas_plester']:.3f} m2</b>"
        })

    return breakdown

# ==========================================
# 4. UI UTAMA (TABEL RAPI)
# ==========================================
def render_boq_tab(data_proyek):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        api_key = st.text_input("🔑 Google API Key (Untuk Tanya AI):", type="password")
    
    model_ai = None
    if api_key:
        model_ai, _ = get_best_model(api_key)

    # Chatbot
    st.markdown("### 🤖 Asisten QS (Validasi & Tanya Jawab)")
    if "messages" not in st.session_state: st.session_state.messages = []
    
    # Tampilkan hanya history terakhir agar tidak penuh
    for msg in st.session_state.messages[-2:]: 
        st.chat_message(msg["role"]).write(msg["content"])
        
    if prompt := st.chat_input("Contoh: 'Cek galian Saluran 1'"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        if model_ai and data_proyek:
            with st.spinner("Analisa..."):
                ctx = build_system_context(data_proyek)
                res = model_ai.generate_content(f"{ctx}\nUSER: {prompt}")
                st.chat_message("assistant").write(res.text)
                st.session_state.messages.append({"role": "assistant", "content": res.text})

    st.divider()
    
    # REPORT PRINTABLE
    st.header("📑 Back-Up Volume (BoQ Standar Dinas)")
    
    st.markdown("""<style>
    @media print { 
        .stChatInput, [data-testid="stSidebar"], .stChatMessage, header, footer, .no-print {display: none !important;} 
        .boq-card {break-inside: avoid; border: 1px solid #000; margin-bottom: 20px;}
        .boq-table th {background: #eee !important; color: black !important;}
    }
    .boq-table {width:100%; border-collapse: collapse; font-size: 0.85rem;}
    .boq-table th, .boq-table td {border: 1px solid #ddd; padding: 5px 8px;}
    .boq-table th {background-color: #2c3e50; color: white; text-align: left;}
    </style>""", unsafe_allow_html=True)

    if not data_proyek:
        st.warning("Data Kosong.")
        return

    for idx, item in enumerate(data_proyek):
        dim = item.get('dimensi', {})
        tipe = item['tipe']
        
        # 1. Pilih Sketsa CANTIK
        sketch = ""
        if "Saluran Beton" in tipe: sketch = get_sketch_uditch(dim.get('b',0), dim.get('h',0), dim.get('t_cm',0))
        elif "Gorong" in tipe: sketch = get_sketch_box(dim.get('w',0), dim.get('h',0), dim.get('t_cm',0))
        elif "Saluran Batu" in tipe: sketch = get_sketch_trapezoid(dim.get('l_bawah',0), dim.get('h',0), 0)
        else: sketch = "<div style='padding:30px; text-align:center; color:#888;'>Sketsa Struktur Kompleks</div>"
        
        # 2. Tabel LENGKAP
        rows = generate_breakdown(item)
        table_html = """
        <table class="boq-table">
            <thead>
                <tr>
                    <th width="12%">Kode</th>
                    <th width="33%">Uraian Pekerjaan</th>
                    <th width="30%">Rumus / Ket.</th>
                    <th width="25%">Volume</th>
                </tr>
            </thead>
            <tbody>
        """
        for r in rows:
            table_html += f"<tr><td>{r['kode']}</td><td>{r['uraian']}</td><td>{r['rumus']}</td><td style='font-weight:bold;'>{r['hitung']}</td></tr>"
        table_html += "</tbody></table>"

        # 3. Layout Card
        st.markdown(f"""
        <div class="boq-card" style="border:1px solid #ddd; border-radius:8px; margin-bottom:30px; background:white; color:black; overflow:hidden;">
            <div style="background:#2c3e50; color:white; padding:10px 15px; font-weight:bold;">#{idx+1}. {item['nama']} <span style="font-weight:normal; font-size:0.9em; opacity:0.9;">({tipe})</span></div>
            <div style="display:flex; flex-wrap:wrap; align-items:flex-start;">
                <div style="width:250px; text-align:center; padding:20px; border-right:1px dashed #ccc;">
                    {sketch}
                </div>
                <div style="flex:1; padding:20px;">
                    {table_html}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
