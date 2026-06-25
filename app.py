import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Tracker Saham Interaktif", layout="wide")
st.title("📊 Portofolio Saham Live")

# Inisialisasi tempat penyimpanan data di dalam web
if 'porto' not in st.session_state:
    st.session_state.porto = pd.DataFrame(columns=["Kode", "Avg Price", "Lot", "Dividen/Lembar"])

# --- SIDEBAR: INPUT & UPLOAD ---
st.sidebar.header("📁 Load Data Sebelumnya")
uploaded_file = st.sidebar.file_uploader("Upload file CSV Portofolio", type=["csv"])
if uploaded_file is not None:
    st.session_state.porto = pd.read_csv(uploaded_file)
    st.sidebar.success("Data berhasil dimuat!")

st.sidebar.divider()

st.sidebar.header("➕ Tambah / Update Saham")
ticker = st.sidebar.text_input("Kode Saham (contoh: BBCA.JK)").upper()
avg_price = st.sidebar.number_input("Harga Rata-rata (Avg Price) Rp", min_value=0.0, step=50.0)
lots = st.sidebar.number_input("Jumlah Lot", min_value=0, step=1)
div = st.sidebar.number_input("Dividen per Lembar (Rp)", min_value=0.0, step=10.0)

if st.sidebar.button("Simpan Data"):
    if ticker:
        new_data = {"Kode": ticker, "Avg Price": avg_price, "Lot": lots, "Dividen/Lembar": div}
        # Jika saham sudah ada, update datanya. Jika belum, tambahkan baru.
        if ticker in st.session_state.porto["Kode"].values:
            idx = st.session_state.porto.index[st.session_state.porto["Kode"] == ticker][0]
            st.session_state.porto.loc[idx] = new_data
        else:
            st.session_state.porto = pd.concat([st.session_state.porto, pd.DataFrame([new_data])], ignore_index=True)
        st.sidebar.success(f"{ticker} berhasil disimpan!")

# --- MAIN PAGE: KALKULASI & TAMPILAN ---
if not st.session_state.porto.empty:
    st.subheader("Rincian Portofolio Saat Ini")
    
    results = []
    total_modal_all = 0
    total_value_all = 0
    total_div_all = 0
    
    for index, row in st.session_state.porto.iterrows():
        tkr = row["Kode"]
        avg = row["Avg Price"]
        lot = row["Lot"]
        dps = row["Dividen/Lembar"]
        
        try:
            # Tarik harga live
            stock = yf.Ticker(tkr)
            live_price = stock.history(period="1d")['Close'].iloc[-1]
            
            lembar = lot * 100
            modal = avg * lembar
            nilai_sekarang = live_price * lembar
            gain = nilai_sekarang - modal
            gain_pct = (gain / modal * 100) if modal > 0 else 0
            tot_div = dps * lembar
            
            total_modal_all += modal
            total_value_all += nilai_sekarang
            total_div_all += tot_div
            
            results.append({
                "Emiten": tkr.replace(".JK", ""),
                "Lot": lot,
                "Avg Price": f"Rp {avg:,.0f}",
                "Harga Live": f"Rp {live_price:,.0f}",
                "Modal": f"Rp {modal:,.0f}",
                "Nilai Saat Ini": f"Rp {nilai_sekarang:,.0f}",
                "Capital Gain": f"Rp {gain:,.0f} ({gain_pct:.2f}%)",
                "Potensi Dividen": f"Rp {tot_div:,.0f}"
            })
        except Exception as e:
            st.error(f"Gagal menarik data untuk {tkr}.")
            
    # Tampilkan dalam bentuk tabel
    df_results = pd.DataFrame(results)
    st.dataframe(df_results, use_container_width=True)
    
    # Ringkasan Total
    st.divider()
    st.subheader("💰 Ringkasan Keseluruhan")
    c1, c2, c3 = st.columns(3)
    
    total_gain_all = total_value_all - total_modal_all
    total_gain_pct_all = (total_gain_all / total_modal_all * 100) if total_modal_all > 0 else 0
    
    c1.metric("Total Modal", f"Rp {total_modal_all:,.0f}")
    c2.metric("Total Nilai Portofolio", f"Rp {total_value_all:,.0f}")
    c3.metric("Total Capital Gain", f"Rp {total_gain_all:,.0f}", f"{total_gain_pct_all:.2f}%")
    
    c4, c5, c6 = st.columns(3)
    c4.metric("Total Potensi Dividen", f"Rp {total_div_all:,.0f}")
    c5.metric("Total Return (Gain + Div)", f"Rp {(total_gain_all + total_div_all):,.0f}")
    
    # Tombol Download untuk menyimpan data
    st.divider()
    csv = st.session_state.porto.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Data Portofolio (CSV)",
        data=csv,
        file_name='data_portofolio_saham.csv',
        mime='text/csv',
    )
else:
    st.info("Portofolio masih kosong. Silakan tambah saham di menu samping.")