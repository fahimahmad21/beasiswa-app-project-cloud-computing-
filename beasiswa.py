# FILE: beasiswa.py (Preprocessing + FastAPI)

import os
import time
import threading
import pickle
import pandas as pd
import numpy as np
import networkx as nx
from textblob import TextBlob
from datetime import datetime
from fastapi import FastAPI, Query
from typing import List
from collections import Counter
import uvicorn
from sklearn.preprocessing import LabelEncoder, MinMaxScaler

# =============================
# STEP 1: Preprocess Data dan Buat Graph
# =============================

# Load dataset beasiswa
sch = pd.read_csv("Universities_Schoolarships_All_Around_the_World.csv")
sch.drop(columns=['Unnamed: 0'], inplace=True, errors='ignore')
for col in ['title', 'degrees', 'funds', 'location']:
    sch[col] = sch[col].astype(str).str.strip().str.lower()
sch['date'] = pd.to_datetime(sch['date'], errors='coerce')

def encode_degree(degree_text):
    if 'bachelor' in degree_text or 'undergraduate' in degree_text or 's1' in degree_text:
        return 1
    elif 'master' in degree_text or 'graduate' in degree_text or 's2' in degree_text:
        return 2
    elif 'phd' in degree_text or 'doctor' in degree_text or 's3' in degree_text:
        return 3
    else:
        return 0
sch['degree_level_encoded'] = sch['degrees'].apply(encode_degree)

def classify_fund(fund_text):
    fund_text = str(fund_text)
    if 'full' in fund_text:
        return 'full'
    elif 'partial' in fund_text:
        return 'partial'
    elif 'tuition' in fund_text:
        return 'tuition only'
    else:
        return 'other'
sch['fund_type'] = sch['funds'].apply(classify_fund)

# Load dataset mahasiswa
df = pd.read_csv("student-por.csv")
df.columns = df.columns.str.strip()
categorical_cols = df.select_dtypes(include='object').columns
label_encoders = {}
for col in categorical_cols:
    le = LabelEncoder()
    df[col] = le.fit_transform(df[col])
    label_encoders[col] = le

df['G_avg'] = df[['G1', 'G2', 'G3']].mean(axis=1)
df['behavior_score'] = (
    df['freetime'] * 0.2 + (5 - df['goout']) * 0.2 + (5 - df['Dalc']) * 0.3 + (5 - df['Walc']) * 0.2 + df['health'] * 0.1
)
scaler = MinMaxScaler()
numeric_cols = ['age', 'Medu', 'Fedu', 'traveltime', 'studytime','failures', 'famrel', 'freetime', 'goout','Dalc', 'Walc', 'health', 'absences', 'G1', 'G2', 'G3','G_avg', 'behavior_score']
df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
df['degree_level_encoded'] = 1

# Gabungkan & preprocess
data = df.merge(sch[sch['degree_level_encoded'] == 1], on='degree_level_encoded', how='inner')
data['date'] = pd.to_datetime(data['date'], errors='coerce')
data['days_until_deadline'] = (data['date'] - pd.Timestamp.now()).dt.days
text_cols = ['title', 'degrees', 'fund_type', 'location']
for col in text_cols:
    data[col] = data[col].astype(str).str.replace(r'[^a-zA-Z0-9\s\-]', '', regex=True).str.strip().str.lower()

def get_sentiment(text):
    if pd.isna(text): return np.nan
    return TextBlob(text).sentiment.polarity

data['title_sentiment'] = data['title'].apply(get_sentiment)

def extract_study_level(degrees_text):
    degrees_text = str(degrees_text).lower()
    if 'bachelor' in degrees_text:
        return 'Undergraduate'
    elif 'master' in degrees_text:
        return 'Postgraduate'
    elif 'phd' in degrees_text:
        return 'Doctoral'
    else:
        return 'Other'

data['study_level'] = data['degrees'].apply(extract_study_level)
data['student_node'] = "SISWA_" + data.index.astype(str)
data['scholarship_node'] = "BEASISWA_" + data['title'].astype(str).str.replace(' ', '_')
data['is_recommended'] = (
    (data['days_until_deadline'] > 0) &
    (data['fund_type'].isin(['full', 'partial', 'tuition only'])) &
    (data['G_avg'] >= 0.5)
)

# Build Graph
G = nx.DiGraph()
sampled_df = data.sample(frac=1.0)

for _, row in sampled_df.iterrows():
    student = row['student_node']
    scholarship = row['scholarship_node']
    fund_type = str(row['fund_type']).capitalize()
    study_level = str(row['study_level']).capitalize()
    location = str(row['location']).title()
    sentiment = f"Sentiment_{round(row['title_sentiment'], 2)}"

    G.add_node(student, entity='STUDENT')
    G.add_node(scholarship, entity='SCHOLARSHIP')
    G.add_node(fund_type, entity='FUND_TYPE')
    G.add_node(study_level, entity='STUDY_LEVEL')
    G.add_node(location, entity='LOCATION')
    G.add_node(sentiment, entity='SENTIMENT')

    G.add_edge(student, scholarship, relationship='RECOMMENDED_TO')
    G.add_edge(scholarship, fund_type, relationship='HAS_FUND_TYPE')
    G.add_edge(scholarship, study_level, relationship='FOR_LEVEL')
    G.add_edge(scholarship, location, relationship='IN_COUNTRY')
    G.add_edge(scholarship, sentiment, relationship='HAS_SENTIMENT')

# Simpan graph
with open("rekomendasi_beasiswa_graph.pkl", "wb") as f:
    pickle.dump(G, f)

# =============================
# STEP 2: FastAPI App
# =============================

app = FastAPI()

@app.get("/")
def root():
    return {"message": "🚀 API berjalan"}

@app.get("/students")
def get_students() -> List[str]:
    return [n for n, d in G.nodes(data=True) if d.get("entity") == "STUDENT"]

@app.get("/student/{student_id}/recommended")
def get_recommended_scholarships(student_id: str) -> List[str]:
    return [t for s, t, d in G.edges(data=True) if s == student_id and d.get('relationship') == 'RECOMMENDED_TO']

@app.get("/scholarship/{scholarship_id}/info")
def get_scholarship_info(scholarship_id: str) -> dict:
    info = {}
    for s, t, d in G.edges(data=True):
        if s == scholarship_id:
            rel = d.get('relationship')
            info.setdefault(rel, []).append(t)
    return info

@app.get("/country/top")
def top_countries(n: int = 5):
    countries = [t for s, t, d in G.edges(data=True) if d.get('relationship') == 'IN_COUNTRY']
    count = Counter(countries).most_common(n)
    return [{"Negara": c, "Jumlah Beasiswa": jml} for c, jml in count]

@app.get("/student/{student_id}/recommend/custom")
def custom_recommendation(student_id: str, fund_type: str = Query(None), study_level: str = Query(None), location: str = Query(None)) -> List[str]:
    recs = []
    for node, data in G.nodes(data=True):
        if data.get("entity") != "SCHOLARSHIP":
            continue

        matches_fund = True
        matches_level = True
        matches_location = True

        if fund_type:
            matches_fund = any(s == node and d.get("relationship") == "HAS_FUND_TYPE" and t.lower() == fund_type.lower() for s, t, d in G.edges(data=True))
        if study_level:
            matches_level = any(s == node and d.get("relationship") == "FOR_LEVEL" and t.lower() == study_level.lower() for s, t, d in G.edges(data=True))
        if location:
            matches_location = any(s == node and d.get("relationship") == "IN_COUNTRY" and t.lower() == location.lower() for s, t, d in G.edges(data=True))

        if matches_fund and matches_level and matches_location:
            recs.append(node)
    return recs

# =============================
# STEP 3: Jalankan Bersama Streamlit
# =============================
def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000)

def run_streamlit():
    os.system("streamlit run app.py")

if __name__ == "__main__":
    threading.Thread(target=run_fastapi).start()
    time.sleep(3)
    run_streamlit()
