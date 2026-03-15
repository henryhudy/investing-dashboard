import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    "credentials.json",
    scopes=scope
)

client = gspread.authorize(creds)

sheet = client.open("Portfolio YIS").sheet1

rows = sheet.get("A1:L")
rows = [r for r in rows if any(r)]
headers = rows[0]
data = []
for row in rows[1:]:
    record = dict(zip(headers, row))
    data.append(record)

df = pd.DataFrame(data)

print(df)