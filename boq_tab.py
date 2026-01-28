import streamlit as st
import pandas as pd
import google.generativeai as genai
import math

# --- 1. MODUL PENGGAMBAR SKETSA (SVG GENERATOR) ---
def get_sketch_uditch(b, h, t_cm):
    """Membuat Sketsa U-Ditch Sederhana dengan SVG"""
    # Scaling untuk tampilan layar (bukan ukuran asli)
    scale = 100 
    # Dimensi visual
    w_inner = b * scale if b > 0 else 50
    h_inner = h * scale if h > 0 else 50
    t_vis = max(10, t_cm * 2) # tebal visual
    
    w_outer = w_inner + (2 * t_vis)
    h_outer = h_inner + t_vis
    
    svg_code = f"""
    <svg width="250" height="200" viewBox="0 0 {w_outer+50} {h_outer+50}" xmlns="http://www.w3.org/2000/svg">
        <style>
            .concrete {{ fill: #bdc3c7; stroke: #2c3e50; stroke-width: 2; }}
            .dim-line {{ stroke: #e74c3c; stroke-width: 1; }}
            .dim-text {{ font-family: Arial; font-size: 12px; fill: #c0392b; }}
        </style>
        
        <path d="M0,0 L{w_outer},0 L{w_outer},{h_outer} L{w_outer-t_vis},{h_outer} L{w_outer-t_vis},{t_vis} L{t_vis},{t_vis} L{t_vis},{h_outer} L0,{h_outer} Z" class="concrete" transform="translate(10,10)" />
        
        <line x1="{10+t_vis}" y1="{10+t_vis/2}" x2="{10+w_outer-t_vis}" y2="{10+t_vis/2}" class="dim-line" />
        <text x="{10+w_outer/2}" y="{10+t_vis/2+4}" class="dim-text" text-anchor="middle">B = {b} m</text>
        
        <line x1="5" y1="10" x2="5" y2="{10+h_outer}" class="dim-line" />
        <text x="0" y="{10+h_outer/2}" class="dim-text" transform="rotate(-90, 0, {10+h_outer/2})" text-anchor="middle">H = {h} m</text>
        
        <text x="{10+w_outer}" y="{10+h_outer}" class="dim-text">t = {t_cm} cm</text>
    </svg>
    """
    return svg_code

def get_sketch_trapezoid(b, h, m, t_cm):
    """Membuat Sketsa Trapesium Sederhana"""
    scale = 80
    b_vis = b * scale
    h_vis = h * scale
    m_vis = m * h_vis # Alas horizontal segitiga
    t_vis = 10 
    
    top_width = b_vis + (2 * m_vis)
    
    svg_code = f"""
    <svg width="300" height="200" viewBox="-50 -20 {top_width+100} {h_vis+50}" xmlns="http://www.w3.org/2000/svg">
        <style> .concrete {{ fill: #95a5a6; stroke: #2c3e50; stroke-width: 2; fill-opacity: 0.5; }} </style>
        <polygon points="0,0 {top_width},0 {b_vis+m_vis},{h_vis} {m_vis},{h_vis}" class="concrete" />
        <text x="{top_width/2}" y="-5" text-anchor="middle" fill="red" font-size="12">L.Atas</text>
        <text x="{top_width/2}" y="{h_vis+15}" text-anchor="middle" fill="red" font-size="12">B = {b} m</text>
        <line x1="{top_width/2}" y1="0" x2="{top_width/2}" y2="{h_vis}" stroke="red" stroke-dasharray="4"/>
        <text x="{top_width/2+5}" y="{h_vis/2}" fill="red" font-size="12">H={h}m</text>
    </svg>
    """
    return svg_code

# --- 2. LOGIKA MATEMATIKA SEDERHANA (QS STYLE) ---
def generate_simple_math(item):
    """Menerjemahkan perhitungan Python ke Bahasa Matematika Sederhana"""
    dim = item.get('dimensi', {})
    tipe = item['tipe']
    nama = item['nama']
    vol_data = item['vol']
    
    penjelasan = []
    
    # KASUS 1: SALURAN BETON (U-DITCH / BOX)
    if "Saluran Beton" in tipe or "Gorong" in tipe:
        h = dim.get('h', 0)
        b = dim.get('b', 0) if 'b' in dim else dim.get('w', 0) # Handle w for box
        t_cm = dim.get('t_cm', 0)
        p = dim.get('panjang', 0)
        
        t_m = t_cm / 100
        
        # Logika Luas Penampang (Metode Pengurangan Luas)
        # Luas Total (Luar) = (B + 2t) * (H + t) -> Untuk U-Ditch
        # Luas Dalam (Lubang) = B * H
        
        b_luar = b + (2 * t_m)
        h_luar = h + t_m # Asumsi bawah saja ada beton, atas terbuka
        
        # Cek jika Box Culvert (tutup atas ada)
        if "Gorong" in tipe:
            h_luar = h + (2 * t_m)
            rumus_judul = "Rumus Box: (Luas Luar - Luas Dalam) x Panjang"
        else:
            rumus_judul = "Rumus U-Ditch: (Luas Luar - Luas Dalam) x Panjang"

        luas_luar_txt = f"({b} + {2*t_m:.2f}) x ({h} + {t_m:.2f})"
        luas_dalam_txt = f"{b} x {h}"
        
        penjelasan.append({
            "title": "A. Volume Beton Struktur",
            "sketch": get_sketch_uditch(b, h, t_cm),
            "steps": [
                f"<b>Konsep:</b> {rumus_judul}",
                f"1. Luas Penampang Beton = (L.Luar) - (L.Dalam)",
                f"&nbsp;&nbsp;&nbsp;= [{luas_luar_txt}] - [{luas_dalam_txt}]",
                f"&nbsp;&nbsp;&nbsp;= {((b+2*t_m)*h_luar):.3f} m2 - {(b*h):.3f} m2",
                f"&nbsp;&nbsp;&nbsp;= <b>{((b+2*t_m)*h_luar - (b*h)):.3f} m2</b>",
                f"2. Volume Total = Luas Penampang x Panjang Saluran",
                f"&nbsp;&nbsp;&nbsp;= {((b+2*t_m)*h_luar - (b*h)):.3f} m2 x {p} m",
                f"&nbsp;&nbsp;&nbsp;= <b>{vol_data['vol_beton']:.3f} m3</b>"
            ]
        })
        
    # KASUS 2: SALURAN BATU / TRAPESIUM
    elif "Saluran Batu" in tipe:
        h = dim.get('h', 0)
        la = dim.get('l_atas', 0)
        lb = dim.get('l_bawah', 0)
        p = dim.get('panjang', 0)
        
        penjelasan.append({
            "title": "A. Volume Pasangan Batu",
            "sketch": get_sketch_trapezoid(lb, h, 0, 0),
            "steps": [
                f"<b>Konsep:</b> Luas Trapesium x Panjang",
                f"1. Luas Penampang = ((Lebar Atas + Lebar Bawah) / 2) x Tinggi",
                f"&nbsp;&nbsp;&nbsp;= (({la} + {lb}) / 2) x {h}",
                f"&nbsp;&nbsp;&nbsp;= <b>{((la+lb)/2 * h):.3f} m2</b>",
                f"2. Volume Total = Luas x Panjang",
                f"&nbsp;&nbsp;&nbsp;= {((la+lb)/2 * h):.3f} x {p}",
                f"&nbsp;&nbsp;&nbsp;= <b>{vol_data['vol_batu']:.3f} m3</b>"
            ]
        })
        
    # KASUS 3: TERJUNAN / LAINNYA
    else:
        penjelasan.append({
            "title": "A. Volume Struktur (Kompleks)",
            "sketch": "",
            "steps": [
                f"Perhitungan menggunakan metode elemen hingga (Finite Element) atau rumus USBR kompleks.",
                f"Total Beton: <b>{vol_data.get('vol_beton',0):.3f} m3</b>"
            ]
        })

    return penjelasan


# --- 3. RENDER TAB UTAMA ---
def render_boq_tab(data_proyek):
    st.header("📑 Laporan Back-Up Data & Sketsa Volume")
    st.caption("Mode: Laporan Siap Cetak (Printable)")

    if not data_proyek:
        st.warning("Belum ada data proyek.")
        return

    # --- CSS AGAR TABEL RAPI & BISA DI PRINT ---
    st.markdown("""
        <style>
        @media print {
            /* Sembunyikan elemen Streamlit saat print */
            header, footer, .stSidebar, .stButton { display: none !important; }
            /* Atur lebar halaman print */
            .report-container { width: 100% !important; margin: 0 !important; }
            /* Page break agar per item tidak terpotong */
            .item-container { page-break-inside: avoid; margin-bottom: 20px; border-bottom: 2px solid #000; padding-bottom: 20px; }
        }
        
        .report-container { font-family: 'Arial', sans-serif; color: #000; }
        .item-header { background-color: #2c3e50; color: white; padding: 10px; border-radius: 5px; margin-top: 20px; }
        .math-step { font-family: 'Consolas', 'Courier New', monospace; background-color: #f8f9fa; padding: 5px; border-left: 3px solid #2980b9; margin: 2px 0; }
        .vol-box { float: right; background-color: #ecf0f1; padding: 10px; border: 1px solid #bdc3c7; border-radius: 5px; font-weight: bold; }
        .sketch-box { text-align: center; margin: 10px; padding: 10px; border: 1px dashed #ccc; }
        </style>
    """, unsafe_allow_html=True)

    # --- GENERATE LAPORAN HTML ---
    html_content = '<div class="report-container">'
    
    for idx, item in enumerate(data_proyek):
        no = idx + 1
        nama = item['nama']
        tipe = item['tipe']
        
        # Generate Penjelasan Matematika & Sketsa
        math_expl = generate_simple_math(item)
        
        # Header Item
        html_content += f"""
        <div class="item-container">
            <div class="item-header">
                <h3>#{no}. {nama} <span style="font-size:0.8em; font-weight:normal">({tipe})</span></h3>
            </div>
            <table style="width:100%; border-collapse: collapse; margin-top:10px;">
                <tr>
                    <td style="width: 40%; vertical-align: top; border-right: 1px solid #ddd;">
                        <div class="sketch-box">
                            <strong>Sketsa Penampang</strong><br>
                            {math_expl[0]['sketch'] if math_expl else 'Tidak ada sketsa'}
                        </div>
                    </td>
                    <td style="width: 60%; vertical-align: top; padding-left: 15px;">
        """
        
        # Body Perhitungan
        for segment in math_expl:
            html_content += f"<h4>{segment['title']}</h4>"
            for step in segment['steps']:
                html_content += f"<div class='math-step'>{step}</div>"
        
        html_content += """
                    </td>
                </tr>
            </table>
        </div>
        """
        
    html_content += "</div>"
    
    # Render ke Streamlit
    st.markdown(html_content, unsafe_allow_html=True)
    
    st.divider()
    st.info("💡 **Tips Cetak:** Tekan `Ctrl + P` (atau Cmd + P di Mac) di browser Anda. Pilih 'Save as PDF' untuk menyimpan laporan rapi beserta sketsanya.")
