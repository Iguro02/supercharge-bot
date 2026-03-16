import gspread
from google.oauth2.service_account import Credentials

scopes = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = Credentials.from_service_account_file(
    "credentials/google_service_account.json", scopes=scopes
)
gc = gspread.authorize(creds)
sh = gc.open_by_key("1Gy7BsLy1ZnWqJ9jyS2KgFUn46znP5AyEm6Y0vjzyEVQ")
sh.sheet1.append_row(["Test", "test@email.com", "Solar", "Telegram", "test_chat"])
print("Row written successfully!")