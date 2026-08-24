import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Manajemen Keuangan Bulanan", layout="wide")

BULAN_LIST = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

# --- KONEKSI GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_transaksi():
    try:
        df = conn.read(worksheet="Transaksi", ttl=0) # ttl=0 agar selalu realtime
        if not df.empty and 'Tanggal' in df.columns:
            df['Tanggal'] = pd.to_datetime(df['Tanggal']).dt.date
            df['Jumlah'] = pd.to_numeric(df['Jumlah'], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame(columns=['Tanggal', 'Tipe', 'Kategori', 'Jumlah', 'Keterangan', 'Bank'])

def load_kategori():
    try:
        df = conn.read(worksheet="Kategori", ttl=0)
        if not df.empty and 'Persentase' in df.columns:
            df['Persentase'] = pd.to_numeric(df['Persentase'], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame(columns=['Tipe', 'Kategori', 'Persentase'])

def save_transaksi(df):
    df_copy = df.copy()
    if not df_copy.empty:
        df_copy['Tanggal'] = pd.to_datetime(df_copy['Tanggal']).dt.strftime('%Y-%m-%d')
    conn.update(worksheet="Transaksi", data=df_copy)

def save_kategori(df):
    conn.update(worksheet="Kategori", data=df)

# Init State
if 'df_transaksi' not in st.session_state:
    st.session_state.df_transaksi = load_transaksi()

if 'df_kategori' not in st.session_state:
    st.session_state.df_kategori = load_kategori()

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard Visualisasi", 
    "➕ Input & Edit Transaksi", 
    "⚙️ Pengaturan Kategori & Alokasi",
    "📜 Riwayat & Export"
])

# ==========================================
# TAB 1: DASHBOARD VISUALISASI
# ==========================================
with tab1:
    st.title("📊 Dashboard Keuangan Bulanan")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        selected_year = st.selectbox("Pilih Tahun", [2024, 2025, 2026, 2027], index=2, key="dash_year")
    with col_f2:
        selected_month_name = st.selectbox("Pilih Bulan", BULAN_LIST, index=8, key="dash_month")
    
    month_idx = BULAN_LIST.index(selected_month_name) + 1

    df_trans = st.session_state.df_transaksi.copy()
    if not df_trans.empty and 'Tanggal' in df_trans.columns:
        df_trans['Tanggal_DT'] = pd.to_datetime(df_trans['Tanggal'])
        df_filtered = df_trans[(df_trans['Tanggal_DT'].dt.year == selected_year) & (df_trans['Tanggal_DT'].dt.month == month_idx)]
    else:
        df_filtered = pd.DataFrame()

    total_income = df_filtered[df_filtered['Tipe'] == 'Pemasukan']['Jumlah'].sum() if not df_filtered.empty else 0.0
    total_realisasi = df_filtered[df_filtered['Tipe'] == 'Pengeluaran']['Jumlah'].sum() if not df_filtered.empty else 0.0
    saldo = total_income - total_realisasi

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Income", f"Rp {total_income:,.0f}")
    m2.metric("Total Realisasi", f"Rp {total_realisasi:,.0f}")
    m3.metric("Saldo Akhir", f"Rp {saldo:,.0f}")
    pct_used = (total_realisasi / total_income * 100) if total_income > 0 else 0
    m4.metric("% Penggunaan", f"{pct_used:.1f}%")

    st.markdown("---")
    st.subheader(f"Breakdown Alokasi vs Realisasi - {selected_month_name} {selected_year}")

    df_kat_exp = st.session_state.df_kategori[st.session_state.df_kategori['Tipe'] == 'Pengeluaran']
    
    breakdown_data = []
    for _, row in df_kat_exp.iterrows():
        kat = row['Kategori']
        pct = row['Persentase']
        alokasi_val = total_income * pct
        realisasi_val = df_filtered[(df_filtered['Tipe'] == 'Pengeluaran') & (df_filtered['Kategori'] == kat)]['Jumlah'].sum() if not df_filtered.empty else 0.0
        persen_realisasi = (realisasi_val / alokasi_val * 100) if alokasi_val > 0 else 0
        
        breakdown_data.append({
            'Kategori': kat,
            'Persentase Alokasi': f"{pct*100:.1f}%",
            'Target Alokasi (Rp)': alokasi_val,
            'Realisasi (Rp)': realisasi_val,
            'Sisa Alokasi (Rp)': alokasi_val - realisasi_val,
            '% Realisasi': f"{persen_realisasi:.1f}%"
        })

    df_breakdown = pd.DataFrame(breakdown_data)
    st.dataframe(df_breakdown.style.format({
        'Target Alokasi (Rp)': 'Rp {:,.0f}',
        'Realisasi (Rp)': 'Rp {:,.0f}',
        'Sisa Alokasi (Rp)': 'Rp {:,.0f}'
    }), use_container_width=True)

    if not df_breakdown.empty:
        chart_df = df_breakdown.set_index('Kategori')[['Target Alokasi (Rp)', 'Realisasi (Rp)']]
        st.bar_chart(chart_df)

# ==========================================
# TAB 2: INPUT & EDIT TRANSAKSI
# ==========================================
with tab2:
    st.title("➕ Input Transaksi Baru")
    
    list_pemasukan = st.session_state.df_kategori[st.session_state.df_kategori['Tipe'] == 'Pemasukan']['Kategori'].tolist()
    list_pengeluaran = st.session_state.df_kategori[st.session_state.df_kategori['Tipe'] == 'Pengeluaran']['Kategori'].tolist()

    tipe_pilihan = st.radio("Pilih Tipe Transaksi:", ["Pengeluaran", "Pemasukan"], horizontal=True)

    with st.form("form_transaksi", clear_on_submit=True):
        col_i1, col_i2 = st.columns(2)
        with col_i1:
            tanggal = st.date_input("Tanggal Transaksi", datetime.date(2026, 9, 1))
            bank = st.selectbox("Akun / Bank", ["BCA 1", "BCA 2", "BRI", "Cash", "Gopay", "ShopeePay"])
            jumlah = st.number_input("Jumlah (Rp)", min_value=0.0, step=50000.0)
            
        with col_i2:
            if tipe_pilihan == "Pemasukan":
                kategori = st.selectbox("Kategori Pemasukan", list_pemasukan if list_pemasukan else ["Gaji Bulanan"])
            else:
                kategori = st.selectbox("Kategori Pengeluaran", list_pengeluaran if list_pengeluaran else ["Operasional"])
            
            keterangan = st.text_input("Uraian / Keterangan", placeholder="misal: Gaji September / Bayar Kontrakan")

        submit = st.form_submit_button("💾 Simpan Transaksi Baru")

        if submit:
            new_row = pd.DataFrame([{
                'Tanggal': tanggal,
                'Tipe': tipe_pilihan,
                'Kategori': kategori,
                'Jumlah': float(jumlah),
                'Keterangan': keterangan,
                'Bank': bank
            }])
            updated_df = pd.concat([st.session_state.df_transaksi, new_row], ignore_index=True)
            save_transaksi(updated_df)
            st.session_state.df_transaksi = updated_df
            st.success(f"✅ Transaksi ({kategori} - Rp {jumlah:,.0f}) berhasil disimpan ke Google Sheets!")
            st.rerun()

    st.markdown("---")
    st.subheader("📝 Edit / Hapus Data Transaksi Per Bulan")
    
    col_ef1, col_ef2 = st.columns(2)
    with col_ef1:
        filter_edit_year = st.selectbox("Filter Tahun Data", [2024, 2025, 2026, 2027], index=2, key="edit_year")
    with col_ef2:
        filter_edit_month = st.selectbox("Filter Bulan Data", BULAN_LIST, index=8, key="edit_month")

    edit_month_idx = BULAN_LIST.index(filter_edit_month) + 1

    df_full = st.session_state.df_transaksi.copy()
    if not df_full.empty and 'Tanggal' in df_full.columns:
        df_full['Tanggal_DT'] = pd.to_datetime(df_full['Tanggal'])
        df_month_subset = df_full[
            (df_full['Tanggal_DT'].dt.year == filter_edit_year) & 
            (df_full['Tanggal_DT'].dt.month == edit_month_idx)
        ].drop(columns=['Tanggal_DT'])
    else:
        df_month_subset = pd.DataFrame(columns=['Tanggal', 'Tipe', 'Kategori', 'Jumlah', 'Keterangan', 'Bank'])

    st.caption(f"Menampilkan transaksi bulan **{filter_edit_month} {filter_edit_year}**.")

    edited_subset = st.data_editor(
        df_month_subset,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Tanggal": st.column_config.DateColumn("Tanggal", format="YYYY-MM-DD"),
            "Jumlah": st.column_config.NumberColumn("Jumlah (Rp)", format="Rp %d"),
            "Tipe": st.column_config.SelectboxColumn("Tipe", options=["Pemasukan", "Pengeluaran"]),
            "Kategori": st.column_config.SelectboxColumn("Kategori", options=list_pemasukan + list_pengeluaran),
            "Bank": st.column_config.SelectboxColumn("Bank", options=["BCA 1", "BCA 2", "BRI", "Cash", "Gopay", "ShopeePay"])
        },
        key="editor_transaksi_bulan"
    )

    if st.button("💾 Simpan Perubahan Tabel Bulan Ini"):
        df_other_months = df_full[
            ~((df_full['Tanggal_DT'].dt.year == filter_edit_year) & 
              (df_full['Tanggal_DT'].dt.month == edit_month_idx))
        ].drop(columns=['Tanggal_DT'])
        
        final_df = pd.concat([df_other_months, edited_subset], ignore_index=True)
        save_transaksi(final_df)
        st.session_state.df_transaksi = final_df
        st.success("✅ Data transaksi berhasil diperbarui!")
        st.rerun()

# ==========================================
# TAB 3: PENGATURAN KATEGORI & ALOKASI
# ==========================================
with tab3:
    st.title("⚙️ Pengaturan Kategori & Persentase Alokasi")
    
    edited_kategori = st.data_editor(
        st.session_state.df_kategori,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Tipe": st.column_config.SelectboxColumn("Tipe Transaksi", options=["Pemasukan", "Pengeluaran"]),
            "Kategori": st.column_config.TextColumn("Nama Kategori"),
            "Persentase": st.column_config.NumberColumn("Persentase (contoh: 0.10 untuk 10%)", format="%.2f", min_value=0.0, max_value=1.0)
        },
        key="editor_kategori"
    )

    total_pct = edited_kategori[edited_kategori['Tipe'] == 'Pengeluaran']['Persentase'].sum() * 100
    st.info(f"Total Persentase Alokasi Pengeluaran: **{total_pct:.1f}%**")

    if st.button("💾 Simpan Pengaturan Kategori"):
        save_kategori(edited_kategori)
        st.session_state.df_kategori = edited_kategori
        st.success("✅ Daftar kategori berhasil disimpan!")
        st.rerun()

# ==========================================
# TAB 4: RIWAYAT & EXPORT
# ==========================================
with tab4:
    st.title("📜 Riwayat & Export Transaksi")
    
    col_rf1, col_rf2 = st.columns(2)
    with col_rf1:
        filter_riwayat_year = st.selectbox("Filter Tahun", [2024, 2025, 2026, 2027], index=2, key="riwayat_year")
    with col_rf2:
        filter_riwayat_month = st.selectbox("Filter Bulan", ["Semua Bulan"] + BULAN_LIST, index=9, key="riwayat_month")

    df_riwayat = st.session_state.df_transaksi.copy()
    
    if not df_riwayat.empty and 'Tanggal' in df_riwayat.columns:
        df_riwayat['Tanggal_DT'] = pd.to_datetime(df_riwayat['Tanggal'])
        
        if filter_riwayat_month != "Semua Bulan":
            r_month_idx = BULAN_LIST.index(filter_riwayat_month) + 1
            df_filtered_riwayat = df_riwayat[
                (df_riwayat['Tanggal_DT'].dt.year == filter_riwayat_year) & 
                (df_riwayat['Tanggal_DT'].dt.month == r_month_idx)
            ].drop(columns=['Tanggal_DT'])
        else:
            df_filtered_riwayat = df_riwayat[
                df_riwayat['Tanggal_DT'].dt.year == filter_riwayat_year
            ].drop(columns=['Tanggal_DT'])
            
        if not df_filtered_riwayat.empty:
            st.dataframe(df_filtered_riwayat.style.format({'Jumlah': 'Rp {:,.0f}'}), use_container_width=True)
            
            csv_data = df_filtered_riwayat.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 Export Data ({filter_riwayat_month} {filter_riwayat_year}) ke CSV",
                data=csv_data,
                file_name=f"riwayat_keuangan_{filter_riwayat_month}_{filter_riwayat_year}.csv",
                mime='text/csv'
            )
        else:
            st.info(f"Tidak ada data transaksi untuk {filter_riwayat_month} {filter_riwayat_year}.")
    else:
        st.info("Belum ada data transaksi yang tersimpan.")
