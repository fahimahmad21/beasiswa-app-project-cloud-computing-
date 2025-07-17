import streamlit as st
import requests
import pandas as pd

API_BASE = "http://localhost:8000"  # Ganti jika pakai ngrok

st.set_page_config(page_title="🎓 Rekomendasi Beasiswa", layout="wide")
st.title("🎓 Sistem Rekomendasi Beasiswa")
st.markdown("Terintegrasi dengan FastAPI + Streamlit")

with st.sidebar:
    st.header("🧑‍🏫 Pilih Mahasiswa")
    student_list = requests.get(f"{API_BASE}/students").json()
    student_id = st.selectbox("Student ID", student_list)
    if st.button("🔁 Muat Ulang"):
        st.rerun()

st.subheader("📌 Beasiswa Direkomendasikan")
recs = requests.get(f"{API_BASE}/student/{student_id}/recommended").json()
if recs:
    st.success(f"📄 Total {len(recs)} beasiswa direkomendasikan untuk {student_id}.")
    for idx, scholarship_id in enumerate(recs, 1):
        st.markdown(f"**{idx}. {scholarship_id}**")
else:
    st.warning("Tidak ada beasiswa direkomendasikan.")

if recs:
    st.subheader("🔍 Detail Beasiswa Pertama")
    info = requests.get(f"{API_BASE}/scholarship/{recs[0]}/info").json()
    for key, value in info.items():
        st.markdown(f"**{key.replace('_', ' ').title()}**: {', '.join(value)}")

st.subheader("🌍 Negara Tujuan Populer")
top_locs = requests.get(f"{API_BASE}/country/top").json()
df = pd.DataFrame(top_locs)
st.dataframe(df.set_index("Negara"))

# ===============================
# 🔍 Filter Rekomendasi Kustom
# ===============================
with st.sidebar:
    st.header("🔍 Filter Rekomendasi Kustom")
    fund_type = st.selectbox("Tipe Dana", [None, "Full", "Partial", "Tuition only", "Other"])
    study_level = st.selectbox("Jenjang Studi", [None, "Undergraduate", "Master", "PhD"])
    location = st.selectbox("Lokasi", [
        None,
        "India",
        "United-States",
        "Pakistan",
        "United-Kingdom",
        "Canada",
        "South-Africa",
        "Nigeria",
        "Europe"
    ])

    result = []
    if st.button("🎯 Cari Rekomendasi"):
        query = f"/student/{student_id}/recommend/custom?"
        if fund_type:
            query += f"&fund_type={fund_type}"
        if study_level:
            query += f"&study_level={study_level}"
        if location:
            query += f"&location={location}"
        result = requests.get(f"{API_BASE}{query}").json()

        st.subheader("📋 Hasil Rekomendasi Kustom")
        if result:
            for idx, r in enumerate(result, 1):
                st.markdown(f"{idx}. {r}")
        else:
            st.warning("Tidak ditemukan beasiswa yang cocok.")

# ===============================
# 📋 Tabel Hasil Rekomendasi Kustom (di bawah negara populer)
# ===============================
st.subheader("📋 Hasil Rekomendasi Kustom (Tabel)")
if 'result' in locals() and result:
    result_df = pd.DataFrame({"Scholarship ID": result})
    st.dataframe(result_df)
elif 'result' in locals():
    st.info("Tidak ada beasiswa yang cocok ditampilkan dalam tabel.")
