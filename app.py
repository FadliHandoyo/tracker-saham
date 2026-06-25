import streamlit as st
import yfinance as yf
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import pytz
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Tracker Saham & Analitik", layout="wide")
st.title("📊 Portofolio & Analitik Saham")

tz_wib = pytz.timezone('Asia/Jakarta')
list_bulan = ["-", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

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
    ws_porto = sh.worksheet("Portofolio")
    ws_sejarah = sh.worksheet("Sejarah")
except Exception as e:
    st.error(f"Gagal terhubung ke Google Sheets. Pastikan nama sheet adalah 'Portofolio' dan 'Sejarah'. Error: {e}")
    st.stop()

def load_porto():
    records = ws_porto.get_all_records()
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=["Kode", "Avg Price", "Lot", "Dividen/Lembar", "Bulan Dividen", "Tahun Dividen", "Total Dividen Cair", "Terakhir Update"])
    if not df.empty:
        if "Total Dividen Cair" not in df.columns:
            df["Total Dividen Cair"] = 0.0
        for col in ["Avg Price", "Dividen/Lembar", "Total Dividen Cair"]:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)
        df["Lot"] = pd.to_numeric(df["Lot"], errors='coerce').fillna(0).astype(int)
        for col in ["Bulan Dividen", "Tahun Dividen"]:
            df[col] = df[col].astype(str).replace("", "-").replace("0", "-")
    return df

def load_sejarah():
    records = ws_sejarah.get_all_records()
    return pd.DataFrame(records) if records else pd.DataFrame(columns=["Waktu", "Kode", "Jenis", "Nominal (Rp)", "Keterangan"])

def save_porto(df):
    ws_porto.clear()
    ws_porto.update([df.columns.values.tolist()] + df.values.tolist())

def save_sejarah(df):
    ws_sejarah.clear()
    ws_sejarah.update([df.columns.values.tolist()] + df.values.tolist())

df_porto = load_porto()
df_sejarah = load_sejarah()

# --- SIDEBAR: KONTROL PANEL ---
st.sidebar.header("⚙️ Kelola Portofolio")
menu = st.sidebar.radio("Pilih Aksi:", ["➕ Tambah Baru", "✏️ Edit Saham", "💰 Cairkan Dividen", "🗑️ Hapus Saham"])
st.sidebar.divider()

if menu == "➕ Tambah Baru":
    ticker = st.sidebar.text_input("Kode Saham").upper()
    avg_price = st.sidebar.number_input("Avg Price (Rp)", min_value=0.0, step=50.0)
    lots = st.sidebar.number_input("Jumlah Lot", min_value=0, step=1)
    if st.sidebar.button("Simpan Saham Baru"):
        if ticker:
            waktu_sekarang = datetime.datetime.now(tz_wib).strftime("%Y-%m-%d %H:%M:%S")
            new_porto = {"Kode": ticker, "Avg Price": avg_price, "Lot": lots, "Dividen/Lembar": 0, "Bulan Dividen": "-", "Tahun Dividen": "-", "Total Dividen Cair": 0, "Terakhir Update": waktu_sekarang}
            new_log = {"Waktu": waktu_sekarang, "Kode": ticker, "Jenis": "Beli", "Nominal (Rp)": avg_price * (lots * 100), "Keterangan": "Beli Awal"}
            
            df_porto = pd.concat([df_porto, pd.DataFrame([new_porto])], ignore_index=True)
            df_sejarah = pd.concat([df_sejarah, pd.DataFrame([new_log])], ignore_index=True)
            save_porto(df_porto)
            save_sejarah(df_sejarah)
            st.rerun()

elif menu == "✏️ Edit Saham":
    if not df_porto.empty:
        saham_pilihan = st.sidebar.selectbox("Pilih Saham", df_porto["Kode"].values)
        current_data = df_porto[df_porto["Kode"] == saham_pilihan].iloc[0]
        new_avg = st.sidebar.number_input("Update Avg Price (Rp)", value=float(current_data["Avg Price"]), step=50.0)
        new_lot = st.sidebar.number_input("Update Jumlah Lot", value=int(current_data["Lot"]), step=1)
        
        st.sidebar.markdown("**Input Jadwal Dividen Mendatang**")
        new_div = st.sidebar.number_input("Dividen per Lembar (Rp)", value=float(current_data["Dividen/Lembar"]), step=10.0)
        old_month = str(current_data["Bulan Dividen"])
        idx_month = list_bulan.index(old_month) if old_month in list_bulan else 0
        new_month = st.sidebar.selectbox("Bulan Pembagian", list_bulan, index=idx_month)
        new_year = st.sidebar.text_input("Tahun Pembagian", value=str(current_data["Tahun Dividen"]))
        
        if st.sidebar.button("Update Data"):
            waktu_sekarang = datetime.datetime.now(tz_wib).strftime("%Y-%m-%d %H:%M:%S")
            idx = df_porto.index[df_porto["Kode"] == saham_pilihan][0]
            df_porto.at[idx, "Avg Price"] = new_avg
            df_porto.at[idx, "Lot"] = new_lot
            df_porto.at[idx, "Dividen/Lembar"] = new_div
            df_porto.at[idx, "Bulan Dividen"] = new_month
            df_porto.at[idx, "Tahun Dividen"] = new_year
            df_porto.at[idx, "Terakhir Update"] = waktu_sekarang
            
            new_log = {"Waktu": waktu_sekarang, "Kode": saham_pilihan, "Jenis": "Update", "Nominal (Rp)": new_avg * (new_lot * 100), "Keterangan": "Update Lot/Harga/Jadwal"}
            df_sejarah = pd.concat([df_sejarah, pd.DataFrame([new_log])], ignore_index=True)
            save_porto(df_porto)
            save_sejarah(df_sejarah)
            st.rerun()

elif menu == "💰 Cairkan Dividen":
    if not df_porto.empty:
        saham_pilihan = st.sidebar.selectbox("Pilih Saham yg Bagi Dividen", df_porto["Kode"].values)
        nominal_cair = st.sidebar.number_input("Total Rupiah Masuk Rekening (Rp)", min_value=0.0, step=1000.0)
        
        if st.sidebar.button("Catat Dividen Cair!"):
            waktu_sekarang = datetime.datetime.now(tz_wib).strftime("%Y-%m-%d %H:%M:%S")
            idx = df_porto.index[df_porto["Kode"] == saham_pilihan][0]
            
            df_porto.at[idx, "Total Dividen Cair"] += nominal_cair
            df_porto.at[idx, "Dividen/Lembar"] = 0
            df_porto.at[idx, "Bulan Dividen"] = "-"
            df_porto.at[idx, "Tahun Dividen"] = "-"
            df_porto.at[idx, "Terakhir Update"] = waktu_sekarang
            
            new_log = {"Waktu": waktu_sekarang, "Kode": saham_pilihan, "Jenis": "Dividen", "Nominal (Rp)": nominal_cair, "Keterangan": "Dividen Cair Masuk"}
            df_sejarah = pd.concat([df_sejarah, pd.DataFrame([new_log])], ignore_index=True)
            save_porto(df_porto)
            save_sejarah(df_sejarah)
            st.rerun()

elif menu == "🗑️ Hapus Saham":
    if not df_porto.empty:
        saham_to_delete = st.sidebar.selectbox("Pilih saham", df_porto["Kode"].values)
        if st.sidebar.button("Hapus Permanen", type="primary"):
            df_porto = df_porto[df_porto["Kode"] != saham_to_delete]
            save_porto(df_porto)
            st.rerun()

# --- PENGAMBILAN DATA LIVE (Global agar bisa dipakai di kedua Tab) ---
results_tabel = []
results_grafik = []

total_modal_all = total_value_all = total_div_potensi_all = total_div_cair_all = 0

if not df_porto.empty:
    for index, row in df_porto.iterrows():
        tkr, avg, lot = row["Kode"], row["Avg Price"], row["Lot"]
        dps, b_div, t_div = row["Dividen/Lembar"], row["Bulan Dividen"], row["Tahun Dividen"]
        tot_cair = row.get("Total Dividen Cair", 0.0)
        try:
            live_price = yf.Ticker(tkr).history(period="1d")['Close'].iloc[-1]
            lembar = lot * 100
            modal, nilai_sekarang = avg * lembar, live_price * lembar
            gain = nilai_sekarang - modal
            gain_pct = (gain / modal * 100) if modal > 0 else 0
            tot_div_potensi = dps * lembar
            total_return_saham = gain + tot_cair
            
            total_modal_all += modal
            total_value_all += nilai_sekarang
            total_div_potensi_all += tot_div_potensi
            total_div_cair_all += tot_cair
            jadwal_div = f"{b_div} {t_div}" if b_div != "-" and t_div != "-" else "-"
            
            # Data untuk tabel (format Rupiah)
            results_tabel.append({
                "Emiten": tkr.replace(".JK", ""), "Lot": lot, "Avg Price": f"Rp {avg:,.0f}",
                "Harga Live": f"Rp {live_price:,.0f}", "Modal": f"Rp {modal:,.0f}",
                "Nilai Saat Ini": f"Rp {nilai_sekarang:,.0f}", "Capital Gain": f"Rp {gain:,.0f} ({gain_pct:.2f}%)",
                "Riwayat Dividen Cair": f"Rp {tot_cair:,.0f}", "Potensi Dividen": f"Rp {tot_div_potensi:,.0f} ({jadwal_div})"
            })
            
            # Data untuk grafik (format Angka murni)
            results_grafik.append({
                "Emiten": tkr.replace(".JK", ""),
                "Capital Gain": gain,
                "Dividen Cair": tot_cair,
                "Total Return": total_return_saham
            })
        except Exception as e:
            pass

# --- MAIN PAGE: TABS ---
tab1, tab2 = st.tabs(["📊 Live Portofolio", "📈 Analitik & Buku Sejarah"])

with tab1:
    if results_tabel:
        st.dataframe(pd.DataFrame(results_tabel), use_container_width=True)
        st.divider()
        st.subheader("💰 Ringkasan Kinerja Keseluruhan")
        c1, c2, c3 = st.columns(3)
        total_gain_all = total_value_all - total_modal_all
        total_return_real = total_gain_all + total_div_cair_all
        
        c1.metric("Total Modal", f"Rp {total_modal_all:,.0f}")
        c2.metric("Nilai Portofolio", f"Rp {total_value_all:,.0f}")
        c3.metric("Capital Gain", f"Rp {total_gain_all:,.0f}")
        
        c4, c5, c6 = st.columns(3)
        c4.metric("Total Dividen Sudah Cair", f"Rp {total_div_cair_all:,.0f}")
        c5.metric("Total Return (Gain + Div)", f"Rp {total_return_real:,.0f}")
        c6.metric("Potensi Dividen Mendatang", f"Rp {total_div_potensi_all:,.0f}")
    else:
        st.info("Portofolio masih kosong atau sedang mengambil data pasar.")

with tab2:
    if results_grafik:
        df_chart = pd.DataFrame(results_grafik)
        
        st.subheader("📈 Kinerja Tiap Saham Saat Ini")
        colA, colB = st.columns(2)
        
        # Grafik Capital Gain
        fig_cg = px.bar(df_chart, x="Emiten", y="Capital Gain", color="Emiten", title="Capital Gain / Loss (Rp)", text_auto='.2s')
        colA.plotly_chart(fig_cg, use_container_width=True)
        
        # Grafik Dividen Cair
        fig_div = px.bar(df_chart, x="Emiten", y="Dividen Cair", color="Emiten", title="Dividen Sudah Cair (Rp)", text_auto='.2s')
        colB.plotly_chart(fig_div, use_container_width=True)
        
        # Grafik Gabungan (Capital Gain + Dividen)
        fig_total = px.bar(df_chart, x="Emiten", y="Total Return", color="Emiten", title="Total Return (Capital Gain + Dividen Cair)", text_auto='.2s')
        st.plotly_chart(fig_total, use_container_width=True)
        
        st.divider()
    else:
        st.info("Belum ada data saham untuk dibuatkan grafik.")

    # Bagian Sejarah
    st.subheader("📒 Buku Sejarah (Ledger Transaksi & Dividen)")
    if not df_sejarah.empty:
        st.dataframe(df_sejarah, use_container_width=True)
    else:
        st.info("Buku sejarah masih kosong. Setiap transaksi dan dividen akan otomatis terekam di sini ke depannya.")
