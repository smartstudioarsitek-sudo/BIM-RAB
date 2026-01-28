import streamlit as st
import pandas as pd
import google.generativeai as genai

def render_boq_tab(data_proyek):
    st.header("📑 Back-Up Data & Bill of Quantities (BoQ)")
    st.caption("Standar Perhitungan Volume: Permen PUPR No. 1 Tahun 2022 / No. 182 Tahun 2025")

    # --- 1. SETUP GOOGLE API ---
    # Cek apakah ada di secrets, kalau tidak ada baru minta input manual
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        # Fallback jika secrets belum disetting
        with st.expander("🤖 Asisten AI (Google Gemini) - Penjelas Rumus"):
            api_key = st.text_input("Masukkan Google API Key:", type="password", help="Dapatkan di aistudio.google.com")
    
    # Konfigurasi Awal
    if api_key:
        try:
            genai.configure(api_key=api_key)
        except Exception as e:
            st.error(f"API Key Error: {e}")

    if not data_proyek:
        st.warning("Belum ada data proyek. Silakan input data di Tab 1.")
        return

    # --- 2. ENGINE GENERATOR BOQ ---
    boq_rows = []
    
    for idx, item in enumerate(data_proyek):
        no_item = idx + 1
        nama = item['nama']
        tipe = item['tipe']
        vol_data = item['vol']
        # Ambil dimensi jika ada
        dim = item.get('dimensi', {}) 

        # Header Item Utama
        boq_rows.append({
            "No": f"**{no_item}**", 
            "Uraian Pekerjaan": f"**{nama}**", 
            "Kode": "", 
            "Rumus / Dimensi": "",
            "Perhitungan": "", 
            "Volume": "", 
            "Satuan": ""
        })

        # --- LOGIKA PENURUNAN RUMUS (BREAKDOWN) ---
        # 1. Galian Tanah
        if vol_data.get('vol_galian', 0) > 0:
            rumus_txt = ""
            calc_txt = ""
            if tipe == "Saluran Beton" and dim:
                h_galian = dim.get('h', 0) + (dim.get('t_cm', 0)/100) + 0.2
                l_bawah_g = dim.get('b', 0) + 2*(dim.get('t_cm', 0)/100) + 0.4
                l_atas_g = l_bawah_g + (2 * 0.5 * h_galian) 
                
                rumus_txt = "((Lb + La)/2) x H x P"
                calc_txt = f"(({l_bawah_g:.2f}+{l_atas_g:.2f})/2) x {h_galian:.2f} x {dim.get('panjang',0)}"
            
            boq_rows.append({
                "No": "", "Uraian Pekerjaan": "  - Galian Tanah Biasa", "Kode": "T.06.a.1",
                "Rumus / Dimensi": rumus_txt if dim else "Analisa Luas x Panjang",
                "Perhitungan": calc_txt if dim else "Sesuai Profil Melintang",
                "Volume": f"{vol_data['vol_galian']:.3f}", "Satuan": "m3"
            })

        # 2. Beton Struktur
        if vol_data.get('vol_beton', 0) > 0:
            rumus_txt = ""
            calc_txt = ""
            if tipe == "Saluran Beton" and dim:
                p = dim.get('panjang', 0)
                h = dim.get('h', 0)
                b = dim.get('b', 0)
                t = dim.get('t_cm', 0)/100
                
                rumus_txt = "((2H + B) x t) x P"
                calc_txt = f"((2x{h} + {b}) x {t}) x {p}"
            
            boq_rows.append({
                "No": "", "Uraian Pekerjaan": "  - Beton Struktur K-225", "Kode": "B.05.a",
                "Rumus / Dimensi": rumus_txt if dim else "Analisa CAD",
                "Perhitungan": calc_txt if dim else "Sesuai Detail Struktur",
                "Volume": f"{vol_data['vol_beton']:.3f}", "Satuan": "m3"
            })

        # 3. Bekisting
        if vol_data.get('luas_bekisting', 0) > 0:
            rumus_txt = ""
            calc_txt = ""
            if tipe == "Saluran Beton" and dim:
                h = dim.get('h', 0)
                p = dim.get('panjang', 0)
                rumus_txt = "(2 x H) x P x 2 Sisi"
                calc_txt = f"(2 x {h}) x {p} x 2"

            boq_rows.append({
                "No": "", "Uraian Pekerjaan": "  - Pasang Bekisting", "Kode": "B.20.a",
                "Rumus / Dimensi": rumus_txt if dim else "Luas Bidang Basah",
                "Perhitungan": calc_txt if dim else "-",
                "Volume": f"{vol_data['luas_bekisting']:.3f}", "Satuan": "m2"
            })

        # 4. Pembesian
        if vol_data.get('berat_besi', 0) > 0:
             boq_rows.append({
                "No": "", "Uraian Pekerjaan": "  - Pembesian (Ratio)", "Kode": "B.17.a",
                "Rumus / Dimensi": "Vol. Beton x Ratio (kg/m3)",
                "Perhitungan": f"{vol_data['vol_beton']:.2f} x Ratio",
                "Volume": f"{vol_data['berat_besi']:.3f}", "Satuan": "kg"
            })

    # --- 3. RENDER DATAFRAME ---
    df_boq = pd.DataFrame(boq_rows)
    
    st.markdown("### 📋 Tabel Perhitungan Volume (BoQ)")
    
    st.markdown("""
    <style>
        .stDataFrame td {font-family: 'Consolas', sans-serif; font-size: 0.9rem;}
        .stDataFrame th {background-color: #2c3e50; color: white;}
    </style>
    """, unsafe_allow_html=True)
    
    st.dataframe(
        df_boq,
        column_config={
            "No": st.column_config.TextColumn("No", width="small"),
            "Uraian Pekerjaan": st.column_config.TextColumn("Uraian Pekerjaan", width="large"),
            "Rumus / Dimensi": st.column_config.TextColumn("Rumus", width="medium"),
            "Perhitungan": st.column_config.TextColumn("Detail Hitungan", width="medium"),
        },
        hide_index=True,
        use_container_width=True
    )

    # --- 4. FITUR TANYA AI ---
    st.divider()
    
    if api_key:
        col_ai1, col_ai2 = st.columns([1, 3])
        
        with col_ai1:
            st.info("**Konsultan Virtual**")
            # Filter hanya item anak (yang punya indentasi/sub-item)
            pilihan_item = [row['Uraian Pekerjaan'] for row in boq_rows if "  -" in str(row['Uraian Pekerjaan'])]
            
            if not pilihan_item:
                st.caption("Tidak ada item detail untuk dianalisa.")
                selected_item = None
            else:
                selected_item = st.selectbox("Pilih Item:", pilihan_item)
                
            ask_btn = st.button("❓ Jelaskan Perhitungan")
            
        with col_ai2:
            if ask_btn and selected_item:
                try:
                    row_data = df_boq[df_boq['Uraian Pekerjaan'] == selected_item].iloc[0]
                    prompt = f"""
                    Bertindaklah sebagai Senior Quantity Surveyor. Jelaskan singkat kepada pemilik proyek:
                    Item: {selected_item}
                    Kode: {row_data['Kode']}
                    Rumus: {row_data['Rumus / Dimensi']}
                    Volume: {row_data['Volume']} {row_data['Satuan']}
                    
                    Jelaskan apa pekerjaan ini dan kenapa rumusnya begitu (secara geometri).
                    """
                    # --- PERUBAHAN DI SINI: MENGGUNAKAN GEMINI 1.5 FLASH ---
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(prompt)
                    st.markdown(f"**Penjelasan Ahli ({selected_item}):**")
                    st.write(response.text)
                except Exception as e:
                    st.error(f"Gagal menghubungi AI: {e}")
    else:
        st.warning("⚠️ API Key belum terdeteksi. Pastikan file secrets.toml sudah benar formatnya.")
