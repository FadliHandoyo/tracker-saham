import streamlit as st
import yfinance as yf
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import pytz

st.set_page_config(page_title="Tracker Saham Otomatis", layout="wide")
st.title("📊 Portofolio Saham Live")

# Zona waktu Indonesia Barat (WIB)
tz_wib = pytz.timezone('Asia/Jakarta')

@st.cache_resource
def get_gspread_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "\\n" in creds_dict["private_key"]:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

try:
    gc = get_gspread_client()
    sheet_url = st.secrets["gsheets"]["spreadsheet_url"]
    sh = gc.open_by_url(sheet_url)
    worksheet = sh.get_worksheet(0)
except Exception as e:
    st.error(f"Gagal terhubung ke Google Sheets. Error: {e}")
    st.stop()

def load_data():
    records = worksheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=["Kode", "Avg Price", "Lot", "Dividen/Lembar", "Terakhir Update"])
    return pd.DataFrame(records)

def save_data(df):
    worksheet.clear()
    data_to_save = [df.columns.values.tolist()] + df.values.tolist()
    worksheet.update(data_to_save)

df_porto = load_data()

# --- SIDEBAR: KONTROL PANEL ---
st.sidebar.header("⚙️ Kelola Portofolio")
menu = st.sidebar.radio("Pilih Aksi:", ["➕ Tambah Baru", "✏️ Edit Saham", "🗑️ Hapus Saham"])

st.sidebar.divider()

if menu == "➕ Tambah Baru":
    st.sidebar.subheader("Input Saham Baru")
    ticker = st.sidebar.text_input("Kode Saham (contoh: BBCA.JK)").upper()
    avg_price = st.sidebar.number_input("Harga Rata-rata (Avg Price) Rp", min_value=0.0, step=50.0)
    lots = st.sidebar.number_input("Jumlah Lot", min_value=0, step=1)
    div = st.sidebar.number_input("Dividen per Lembar (Rp)", min_value=0.0, step=10.0)

    if st.sidebar.button("Simpan Saham Baru"):
        if ticker:
            if not df_porto.empty and ticker in df_porto["Kode"].values:
                st.sidebar.error(f"Saham {ticker} sudah ada! Silakan gunakan menu 'Edit Saham'.")
            else:
                waktu_sekarang = datetime.datetime.now(tz_wib).strftime("%Y-%m-%d %H:%M:%S")
                new_data = {"Kode": ticker, "Avg Price": avg_price, "Lot": lots, "Dividen/Lembar": div, "Terakhir Update": waktu_sekarang}
                df_porto = pd.concat([df_porto, pd.DataFrame([new_data])], ignore_index=True)
                save_data(df_porto)
                st.sidebar.success(f"{ticker} berhasil ditambahkan!")
                st.rerun()

elif menu == "✏️ Edit Saham":
    st.sidebar.subheader("Update Saham Exist")
    if not df_porto.empty:
        saham_pilihan = st.sidebar.selectbox("Pilih Saham", df_porto["Kode"].values)
        
        # Tarik data saat ini sebagai nilai default di form
        current_data = df_porto[df_porto["Kode"] == saham_pilihan].iloc[0]
        
        new_avg = st.sidebar.number_input("Update Avg Price (Rp)", value=float(current_data["Avg Price"]), step=50.0)
        new_lot = st.sidebar.number_input("Update Jumlah Lot", value=int(current_data["Lot"]), step=1)
        new_div = st.sidebar.number_input("Update Dividen (Rp)", value=float(current_data["Dividen/Lembar"]), step=10.0)
        
        if st.sidebar.button("Update Data"):
            waktu_sekarang = datetime.datetime.now(tz_wib).strftime("%Y-%m-%d %H:%M:%S")
            idx = df_porto.index[df_porto["Kode"] == saham_pilihan][0]
            
            df_porto.at[idx, "Avg Price"] = new_avg
            df_porto.at[idx, "Lot"] = new_lot
            df_porto.at[idx, "Dividen/Lembar"] = new_div
            df_porto.at[idx, "Terakhir Update"] = waktu_sekarang
            
            save_data(df_porto)
            st.sidebar.success(f"Data {saham_pilihan} berhasil diupdate!")
            st.rerun()
    else:
        st.sidebar.info("Portofolio kosong. Tambahkan saham terlebih dahulu.")

elif menu == "🗑️ Hapus Saham":
    st.sidebar.subheader("Hapus Data Saham")
    if not df_porto.empty:
        saham_to_delete = st.sidebar.selectbox("Pilih saham yang mau dihapus", df_porto["Kode"].values)
        if st.sidebar.button("Hapus Permanen", type="primary"):
            df_porto = df_porto[df_porto["Kode"] != saham_to_delete]
            save_data(df_porto)
            st.sidebar.success(f"{saham_to_delete} berhasil dihapus!")
            st.rerun()
    else:
        st.sidebar.info("Portofolio sudah kosong.")

# --- MAIN PAGE: KALKULASI & TAMPILAN LIVE ---
if not df_porto.empty:
    st.subheader("Rincian Portofolio Saat Ini")
    
    results = []
    total_modal_all = 0
    total_value_all = 0
    total_div_all = 0
    
    for index, row in df_porto.iterrows():
        tkr = row["Kode"]
        avg = row["Avg Price"]
        lot = row["Lot"]
        dps = row["Dividen/Lembar"]
        terakhir_update = row.get("Terakhir Update", "-")
        
        try:
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
                "Potensi Dividen": f"Rp {tot_div:,.0f}",
                "Terakhir Update": terakhir_update
            })
        except Exception as e:
            st.error(f"Gagal menarik data live untuk {tkr}.")
            
    df_results = pd.DataFrame(results)
    st.dataframe(df_results, use_container_width=True)
    
    st.divider()
    st.subheader("💰 Ringkasan Keseluruhan")
    c1, c2, c3 = st.columns(3)
    
    total_gain_all = total_value_all - total_modal_all
    total_gain_pct_all = (total_gain_all / total_modal_all * 100) if total_modal_all > 0 else 0
    
    c1.metric("Total Modal", f"Rp {total_modal_all:,.0f}")
    c2.metric("Total Nilai Portofolio", f"Rp {total_value_all:,.0f}")
    c3.metric("Total Capital Gain", f"Rp {total_gain_all:,.0f}", f"{total_gain_pct_all:.2f}%")
    
    c4, c5 = st.columns(2)
    c4.metric("Total Potensi Dividen", f"Rp {total_div_all:,.0f}")
    c5.metric("Total Return (Gain + Div)", f"Rp {(total_gain_all + total_div_all):,.0f}")
else:
    st.info("Portofolio masih kosong di Google Sheets. Silakan gunakan menu di samping untuk menambah saham.")
