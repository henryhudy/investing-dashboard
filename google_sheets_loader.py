import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import json

def load_google_sheet_data(sheet_name="Portfolio YIS", range_="A1:L"):
    # Load credentials from Streamlit secrets
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1
    rows = sheet.get(range_)
    rows = [r for r in rows if any(r)]  # Remove empty rows
    if not rows:
        return pd.DataFrame()
    headers = rows[0]
    data = []
    for row in rows[1:]:
        record = dict(zip(headers, row))
        data.append(record)
    df = pd.DataFrame(data)
    if "Current Position Value" in df.columns:
        df["Current Position Value"] = pd.to_numeric(df["Current Position Value"].str.replace(",", ""), errors="coerce")
    return df
