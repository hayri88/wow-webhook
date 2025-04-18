from fastapi import FastAPI
from pydantic import BaseModel
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import datetime
import re

app = FastAPI()

# 🔐 Google OAuth bilgilerin
CLIENT_ID = "741026762528-ttbge9ghamrmvd6qc943aopqedhe1v3v.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REFRESH_TOKEN = "1//03eNXVYcixiqcCgYIARAAGAMSNwF-L9Irf3RI0ma-R4dOsIcQPZT1wyziogAL0brd7AG1l5Y8MQFSbPVgIVEkzqwuloyuXZKoM7Q"
CALENDAR_ID = "b79031f4e7b42a908739d9773febb4e052d3ca6ff1bb385d56fb262bf87e1e0a@group.calendar.google.com"

class EventRequest(BaseModel):
    message: str

@app.post("/add-event")
def add_event(data: EventRequest):
    msg = data.message

    # 📅 Tarih, saat ve müşteri adını ayıklama
    date_match = re.search(r"(\d{1,2} [A-Za-zçğıöşüÇĞİÖŞÜ]+ \d{4})", msg)
    time_match = re.search(r"saat (\d{1,2})([:.]?(\d{2}))?", msg)
    customer_match = re.search(r"^(.+?) müşterisinin", msg)

    if not (date_match and time_match and customer_match):
        return {"error": "Tarih, saat veya müşteri adı bulunamadı."}

    date_str = date_match.group(1)
    time_hour = int(time_match.group(1))
    time_minute = int(time_match.group(3)) if time_match.group(3) else 0
    customer = customer_match.group(1)

    try:
        dt_start = datetime.datetime.strptime(date_str, "%d %B %Y")
    except ValueError:
        try:
            dt_start = datetime.datetime.strptime(date_str, "%d %b %Y")
        except:
            return {"error": "Tarih formatı anlaşılamadı."}

    dt_start = dt_start.replace(hour=time_hour, minute=time_minute)
    dt_end = dt_start + datetime.timedelta(hours=1)

    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )

    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary": f"{customer} – Saha Görevi",
        "description": msg,
        "start": {"dateTime": dt_start.isoformat(), "timeZone": "Europe/Istanbul"},
        "end": {"dateTime": dt_end.isoformat(), "timeZone": "Europe/Istanbul"},
    }

    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return {"status": "added", "event_id": created_event["id"]}
