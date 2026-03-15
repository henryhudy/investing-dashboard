import pandas as pd
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

def load_google_sheet_data(sheet_name="Portfolio YIS"):
    # 1. Load and fix credentials
    creds_info = st.secrets["gcp_service_account"]
    creds_dict = dict(creds_info)
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    creds = Credentials.from_service_account_info(creds_dict, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)
    
    # 2. Open the sheet and get ALL values as a list of lists
    sheet = client.open(sheet_name).sheet1
    all_values = sheet.get_all_values() 
    
    if not all_values:
        return pd.DataFrame()
        
    # 3. Separate headers and data
    headers = all_values[0]
    data = all_values[1:]
    
    # 4. Create DataFrame
    df = pd.DataFrame(data, columns=headers)

    # 5. CLEANUP: Remove columns with empty string headers
    # This specifically fixes the "GSpreadException: duplicates ['']" error
    df = df.loc[:, df.columns != ""]
    
    # 6. CLEANUP: Remove rows that are entirely empty
    df = df.replace('', pd.NA).dropna(how='all')

    # 7. Format numeric columns
    if "Current Position Value" in df.columns:
        df["Current Position Value"] = (
            df["Current Position Value"]
            .astype(str)
            .str.replace(",", "")
            .str.replace("$", "", regex=False)
        )
        df["Current Position Value"] = pd.to_numeric(df["Current Position Value"], errors="coerce")
        
    return df