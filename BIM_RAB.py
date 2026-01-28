import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO
import boq_tab  # <--- Modul BoQ Integrator

# --- 1. SETUP HALAMAN ---
st.set_page_config(page_title="Pro QS V.12: AHSP SDA Bengkulu", layout="wide", page_icon="🏗️")

if 'data_proyek' not in st.session_state:
    st.session_state['data_proyek'] = []

# --- 2. DATABASE AHSP (LENGKAP) ---
class AHSP_Engine:
    @staticmethod
    def get_analisa_detail(hsp_code, prices):
        u_p, u_t, u_m = prices['u_pekerja'], prices['u_tukang'], prices['u_mandor']
        p_sem, p_pas, p_bat = prices['p_semen'], prices['p_pasir'], prices['p_batu']
        p_spl, p_bes, p_kay = prices['p_split'], prices['p_besi'], prices['p_kayu']
        p_pak, p_kaw = prices['p_paku'], prices['p_kawat']

        if hsp_code == "T.06.a.1": 
            return {"kode": "T.06.a.1", "uraian": "Galian Tanah Biasa", "items": [("Pekerja", 0.750, u_p), ("Mandor", 0.025, u_m)]}
        elif hsp_code == "T.14.a": 
            return {"kode": "T.14.a", "uraian": "Timbunan Kembali", "items": [("Pekerja", 0.330, u_p), ("Mandor", 0.010, u_m)]}
        elif hsp_code == "P.01.a": 
            return {"kode": "P.01.a", "uraian": "Pasangan Batu 1:4", "items": [("Pekerja", 1.2, u_p), ("Tukang", 0.6, u_t), ("Mandor", 0.06, u_m), ("Batu Kali", 1.2, p_bat), ("Semen", 163, p_sem), ("Pasir", 0.52, p_pas)]}
        elif hsp_code == "B.05.a": 
            return {"kode": "B.05.a", "uraian": "Beton K-225", "items": [("Pekerja", 1.65, u_p), ("Tukang", 0.275, u_t), ("Mandor", 0.083, u_m), ("Semen", 371, p_sem), ("Pasir", 0.499, p_pas), ("Split", 0.776, p_spl)]}
        elif hsp_code == "B.17.a": 
            return {"kode": "B.17.a", "uraian": "Pembesian", "items": [("Pekerja", 0.007, u_p), ("Tukang", 0.007, u_t), ("Mandor", 0.0004, u_m), ("Besi", 1.05, p_bes), ("Kawat", 0.015, p_kaw)]}
        elif hsp_code == "B.20.a": 
            return {"kode": "B.20.a", "uraian": "Bekisting", "items": [("Pekerja", 0.52, u_p), ("Tukang", 0.26, u_t), ("Mandor", 0.026, u_m), ("Kayu", 0.045, p_kay), ("Paku", 0.3, p_pak), ("Minyak", 0.1, 25000)]}
        elif hsp_code == "T.15.a": 
            return {"kode": "T.15.a", "uraian": "Bongkaran", "items": [("Pekerja", 2.0, u_p), ("Mandor", 0.1, u_m)]}
        elif hsp_code == "P.04.e":
            return {"kode": "P.04.e", "uraian": "Plesteran 1:3", "items": [("Pekerja", 0.3, u_p), ("Tukang", 0.15, u_t), ("Semen", 7.77, p_sem), ("Pasir", 0.024, p_pas)]}
        elif hsp_code == "P.05.a":
            return {"kode": "P.05.a", "uraian": "Siaran 1:2", "items": [("Pekerja", 0.15, u_p), ("Tukang", 0.075, u_t), ("Semen", 6.0, p_sem), ("Pasir", 0.01, p_pas)]}
        
        return {"kode": "N/A", "uraian": "Item N/A", "items": []}

    @staticmethod
    def hitung_harga_satuan(hsp_code, prices, overhead):
        data = AHSP_Engine.get_analisa_detail(hsp_code, prices)
        total = sum([i[1]*i[2] for i in data['items']])
        return total * (1 + overhead/100)

# --- 3. CALCULATOR ENGINEERING (RUMUS KOMPLEKS DIKEMBALIKAN) ---
class Calculator:
    
    # 3.1 BETON STRUKTUR (U-DITCH) - Rumus Galian Trapesium Presisi
    @staticmethod
    def hitung_beton_struktur(h, b, m, panjang, t_cm, dia, jarak, lapis, waste, fc, fy, is_rehab):
        t_m = t_cm / 100
        # Luas Penampang Beton
        luas_luar = (b + 2*(h*math.sqrt(1+m**2)) + 2*t_m) * t_m 
        vol_beton = luas_luar * panjang
        
        # Rumus Galian Presisi (Trapesium dengan Space Kerja 20-40cm)
        space_kerja = 0.4
        lebar_bawah_galian = b + (2 * t_m * math.sqrt(1+m**2)) + (2 * space_kerja)
        tinggi_galian = h + t_m + 0.2 # + lantai kerja
        # Asumsi kemiringan galian tanah 1:0.5 (m_tanah = 0.5)
        m_tanah = 0.5
        lebar_atas_galian = lebar_bawah_galian + (2 * m_tanah * tinggi_galian)
        luas_galian_penampang = ((lebar_bawah_galian + lebar_atas_galian) / 2) * tinggi_galian
        vol_galian = luas_galian_penampang * panjang

        return {
            "vol_beton": vol_beton, "vol_galian": vol_galian, "vol_timbunan": max(0, (vol_galian-vol_beton)*0.45),
            "berat_besi": vol_beton * 115, # Asumsi ratio medium
            "luas_bekisting": (2*h*panjang)*2, "vol_bongkaran": vol_beton if is_rehab else 0
        }
    
    # 3.2 PASANGAN BATU
    @staticmethod
    def hitung_pasangan_batu(h, b, m, panjang, la, lb, tl, is_rehab):
        vol_batu = ((la+lb)/2 * h * 2 + b*tl) * panjang
        return {
            "vol_batu": vol_batu, "vol_galian": vol_batu*1.3, "vol_timbunan": vol_batu*0.35,
            "vol_bongkaran": vol_batu if is_rehab else 0
        }
    
    # 3.3 BOX CULVERT
    @staticmethod
    def hitung_gorong_box(w, h, p, t_cm, is_rehab):
        t_m = t_cm/100
        vol_beton = ((w+2*t_m)*(h+2*t_m)*p) - (w*h*p)
        return {
            "vol_beton": vol_beton, "vol_galian": vol_beton*1.5, "vol_timbunan": vol_beton*0.5,
            "berat_besi": vol_beton * 135, "luas_bekisting": (2*w+2*h)*p, 
            "vol_bongkaran": vol_beton if is_rehab else 0
        }

    # 3.4 TERJUNAN USBR (LOGIKA HIDROLIKA DIKEMBALIKAN)
    @staticmethod
    def hitung_terjunan_usbr(Q, H_total, H_step, B, t_lantai, t_dinding, qa_tanah, mode_hemat, is_rehab):
        # Mencegah pembagian nol
        if H_step <= 0: H_step = 0.1
        if B <= 0: B = 1.0
        if Q <= 0: Q = 0.1 
        
        g = 9.81
        n_steps = math.ceil(H_total / H_step)
        H_real = H_total / n_steps 
        
        # Hidrolika Loncatan Air
        q = Q / B
        V1 = math.sqrt(2 * g * H_real)
        y1 = q / V1
        Fr1 = V1 / math.sqrt(g * y1)
        y2 = 0.5 * y1 * (math.sqrt(1 + 8 * Fr1**2) - 1) # Conjugate Depth
        
        # Penentuan Panjang Kolam (USBR Standard)
        L_kolam_standard = 4.5 * y2 # Aproksimasi umum USBR
        if Fr1 > 4.5: L_kolam_standard = 6.0 * y2 # USBR Type II/III
        
        L_drop = 4.30 * H_real * ((q**2 / (g * H_real**3))**0.27)
        L_total_structure = (L_drop + L_kolam_standard) * n_steps
        
        # Volume Beton Kompleks
        vol_lantai = L_total_structure * B * t_lantai
        vol_dinding = 2 * (L_total_structure * (y2+0.5) * t_dinding)
        vol_beton_total = vol_lantai + vol_dinding
        
        # Stability Check (Uplift)
        W_beton = vol_beton_total * 2.4 # BJ Beton
        Uplift = 0.5 * (y2 + H_real) * L_total_structure * B * 1.0 # Gaya angkat air
        SF = W_beton / Uplift if Uplift > 0 else 99
        status_safe = "AMAN" if SF > 1.2 else "BAHAYA UPLIFT"

        return {
            "info_struktur": f"USBR (Fr={Fr1:.2f}, y2={y2:.2f}m) - {status_safe}",
            "detail_usbr": {"Fr": Fr1, "y1": y1, "y2": y2, "L_total": L_total_structure},
            "vol_beton": vol_beton_total, 
            "vol_batu": 0, 
            "vol_galian": vol_beton_total * 1.4, 
            "vol_timbunan": vol_beton_total * 0.3, 
            "berat_besi": vol_beton_total * 125, # Ratio tinggi untuk bangunan air
            "luas_bekisting": vol_dinding * 2,
            "luas_plester": vol_dinding, 
            "luas_siaran": 0,
            "vol_bongkaran": vol_beton_total if is_rehab else 0
        }

# --- 4. SIDEBAR INPUT HARGA ---
with st.sidebar:
    st.title("💰 Setting Harga Satuan")
    with st.expander("Upah & Bahan", expanded=True):
        u_pekerja = st.number_input("Pekerja (OH)", value=115000.0)
        u_tukang = st.number_input("Tukang (OH)", value=140000.0)
        u_mandor = st.number_input("Mandor (OH)", value=165000.0)
        overhead = st.number_input("Overhead %", value=15.0)
        p_semen = st.number_input("Semen (kg)", value=1650.0)
        p_pasir = st.number_input("Pasir (m3)", value=215000.0)
        p_batu = st.number_input("Batu Kali", value=265000.0)
        p_split = st.number_input("Split", value=325000.0)
        p_besi = st.number_input("Besi (kg)", value=15500.0)
        p_kayu = st.number_input("Kayu (m3)", value=2850000.0)
        p_paku = st.number_input("Paku (kg)", value=20000.0)
        p_kawat = st.number_input("Kawat (kg)", value=22000.0)

    prices = {'u_pekerja':u_pekerja, 'u_tukang':u_tukang, 'u_mandor':u_mandor, 'p_semen':p_semen, 'p_pasir':p_pasir, 'p_batu':p_batu, 'p_split':p_split, 'p_besi':p_besi, 'p_kayu':p_kayu, 'p_paku':p_paku, 'p_kawat':p_kawat}

    # HSP CALCULATOR
    hsp_map = {
        "vol_galian": AHSP_Engine.hitung_harga_satuan("T.06.a.1", prices, overhead),
        "vol_timbunan": AHSP_Engine.hitung_harga_satuan("T.14.a", prices, overhead),
        "vol_beton": AHSP_Engine.hitung_harga_satuan("B.05.a", prices, overhead),
        "vol_batu": AHSP_Engine.hitung_harga_satuan("P.01.a", prices, overhead),
        "berat_besi": AHSP_Engine.hitung_harga_satuan("B.17.a", prices, overhead),
        "luas_bekisting": AHSP_Engine.hitung_harga_satuan("B.20.a", prices, overhead),
        "vol_bongkaran": AHSP_Engine.hitung_harga_satuan("T.15.a", prices, overhead),
        "luas_plester": AHSP_Engine.hitung_harga_satuan("P.04.e", prices, overhead),
        "luas_siaran": AHSP_Engine.hitung_harga_satuan("P.05.a", prices, overhead)
    }

# --- 5. MAIN UI ---
st.title("🏗️ Pro QS V.12: AHSP SDA Bengkulu")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["➕ Input", "📋 List", "📊 RAB", "📑 Analisa", "🧮 Back-Up Volume"])

# === TAB 1: INPUT DATA (FIXED TIPE_FINAL) ===
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Identitas")
        kategori = st.radio("Kategori", ["Saluran (Linear)", "Bangunan Unit"], horizontal=True)
        nama_item = st.text_input("Nama Item", placeholder="Contoh: Saluran A1")
        is_rehab = st.checkbox("Pekerjaan Rehab (Bongkaran)", value=False)
    
    with col2:
        st.subheader("2. Dimensi & Spesifikasi")
        
        # DEFAULT VALUES (PENTING)
        calc = {}
        dimensi_data = {}
        tipe_final = "Umum" # Default biar gak error NameError
        panjang = 0.0

        if kategori == "Saluran (Linear)":
            tipe_kons = st.selectbox("Tipe", ["Beton U-Ditch", "Pasangan Batu"])
            panjang = st.number_input("Panjang (m)", value=50.0)
            tipe_final = "Saluran Beton" if tipe_kons == "Beton U-Ditch" else "Saluran Batu"
            
            if tipe_kons == "Beton U-Ditch":
                h = st.number_input("Tinggi H (m)", value=1.0)
                b = st.number_input("Lebar B (m)", value=0.8)
                t = st.number_input("Tebal (cm)", value=15.0)
                calc = Calculator.hitung_beton_struktur(h, b, 0, panjang, t, 12, 15, 2, 5, 20, 280, is_rehab)
                dimensi_data = {"h":h, "b":b, "t_cm":t, "panjang":panjang}
            else:
                h = st.number_input("Tinggi (m)", value=0.8)
                la = st.number_input("L.Atas (m)", value=0.6)
                lb = st.number_input("L.Bawah (m)", value=0.4)
                calc = Calculator.hitung_pasangan_batu(h, 0.5, 0, panjang, la, lb, 0.2, is_rehab)
                dimensi_data = {"h":h, "l_atas":la, "l_bawah":lb, "panjang":panjang}
        
        else: # Bangunan Unit / Terjunan
            jenis = st.selectbox("Jenis", ["Box Culvert", "Terjunan USBR"])
            
            if jenis == "Box Culvert":
                tipe_final = "Gorong-Gorong"
                w = st.number_input("Lebar (m)", value=1.5)
                h = st.number_input("Tinggi (m)", value=1.5)
                p = st.number_input("Panjang (m)", value=6.0)
                t = st.number_input("Tebal (cm)", value=20.0)
                calc = Calculator.hitung_gorong_box(w, h, p, t, is_rehab)
                dimensi_data = {"w":w, "h":h, "panjang":p, "t_cm":t}
            else: # USBR
                tipe_final = "Terjunan USBR"
                Q = st.number_input("Debit Q (m3/s)", value=2.0)
                H_tot = st.number_input("Tinggi Terjun Total (m)", value=3.0)
                B = st.number_input("Lebar (m)", value=2.0)
                calc = Calculator.hitung_terjunan_usbr(Q, H_tot, 1.5, B, 0.3, 0.25, 150, True, is_rehab)
                dimensi_data = {"Q":Q, "H":H_tot, "B":B}
                st.info(f"Output: {calc.get('info_struktur')}")

        st.divider()
        if st.button("Simpan Item", type="primary"):
            if not nama_item:
                st.error("Isi Nama Item dulu!")
            else:
                # Simpan ke Session State
                st.session_state['data_proyek'].append({
                    "nama": nama_item,
                    "tipe": tipe_final,
                    "dimensi": dimensi_data,
                    "vol": calc
                })
                st.success("Tersimpan!")
                st.rerun()

# === TAB 2: LIST ITEM ===
with tab2:
    if st.session_state['data_proyek']:
        st.dataframe(pd.DataFrame(st.session_state['data_proyek'])[["nama", "tipe"]])
        if st.button("Hapus Data"): st.session_state['data_proyek'] = []; st.rerun()

# === TAB 3: RAB REKAP ===
with tab3:
    st.header("Detail RAB")
    total_rab = 0
    if st.session_state['data_proyek']:
        all_rows = []
        for i, item in enumerate(st.session_state['data_proyek']):
            with st.expander(f"{i+1}. {item['nama']} ({item['tipe']})"):
                for k, v in item['vol'].items():
                    if k in hsp_map and v > 0:
                        hrg = hsp_map[k]
                        tot = v * hrg
                        st.write(f"- {k}: {v:.3f} x {hrg:,.0f} = {tot:,.0f}")
                        total_rab += tot
                        all_rows.append({"Item": item['nama'], "Pekerjaan": k, "Vol": v, "H.Sat": hrg, "Total": tot})
        
        st.success(f"TOTAL RAB: Rp {total_rab:,.0f} (+PPN 11%: Rp {total_rab*1.11:,.0f})")
        
        # Download Excel
        def to_excel(df):
            out = BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            return out.getvalue()
        st.download_button("📥 Download Excel", to_excel(pd.DataFrame(all_rows)), "RAB.xlsx")

# === TAB 4: ANALISA FORMULIR ===
with tab4:
    st.header("Cek Analisa Harga Satuan")
    kode = st.selectbox("Pilih Kode AHSP", ["B.05.a", "T.06.a.1", "B.17.a", "P.01.a"])
    detail = AHSP_Engine.get_analisa_detail(kode, prices)
    st.caption(f"{detail['kode']} - {detail['uraian']}")
    
    df_a = pd.DataFrame(detail['items'], columns=["Komponen", "Koef", "Harga"])
    df_a["Jumlah"] = df_a["Koef"] * df_a["Harga"]
    st.table(df_a)
    st.metric("Harga Satuan (+Overhead)", f"Rp {df_a['Jumlah'].sum() * (1+overhead/100):,.2f}")

# === TAB 5: BACK-UP VOLUME (AI POWERED) ===
with tab5:
    if 'data_proyek' in st.session_state:
        boq_tab.render_boq_tab(st.session_state['data_proyek'])
    else:
        st.info("Input data dulu di Tab 1.")
