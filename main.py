from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timedelta
import re
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

app = FastAPI()

# Türkçe ve Hollandaca ay adları
MONTH_MAP = {
    "ocak": "January", "şubat": "February", "mart": "March", "nisan": "April", "mayıs": "May", "haziran": "June",
    "temmuz": "July", "ağustos": "August", "eylül": "September", "ekim": "October", "kasım": "November", "aralık": "December",
    "januari": "January", "februari": "February", "maart": "March", "april": "April", "mei": "May", "juni": "June",
    "juli": "July", "augustus": "August", "september": "September", "oktober": "October", "november": "November", "december": "December"
}

class EventRequest(BaseModel):
    message: str

@app.post("/add-event")
def add_event(data: EventRequest):
    msg = data.message.lower()

    # Tarih, saat ve müşteri adını ayıklama
    date_match = re.search(r"(\d{1,2}) (\w+) (\d{4})", msg)  # örn. 24 Nisan 2025
    time_match = re.search(r"saat (\d{1,2})[:\.]?(\d{2})", msg)  # örn. saat 14:30 veya 1430
    customer_match = re.search(r"^(.*?) (müşterisinin|ile)", msg)

    if not (date_match and time_match and customer_match):
        return {"error": "Tarih, saat veya müşteri adı bulunamadı."}

    # Ay ismini çevir
    raw_month = date_match.group(2)
    month = MONTH_MAP.get(raw_month.lower())
    if not month:
        return {"error": f"Ay ismi tanınamadı: '{raw_month}'"}

    try:
        date_str = f"{date_match.group(1)} {month} {date_match.group(3)}"
        dt_date = datetime.strptime(date_str, "%d %B %Y")
    except ValueError:
        return {"error": f"Tarih formatı anlaşılamadı: '{date_str}'"}

    try:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
    except:
        return {"error": "Saat formatı anlaşılamadı."}

    customer = customer_match.group(1).strip().capitalize()
    dt_start = dt_date.replace(hour=hour, minute=minute)
    dt_end = dt_start + timedelta(hours=1)

    # Google Calendar ayarları
    CALENDAR_ID = os.getenv("CALENDAR_ID")
    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("CLIENT_SECRET")
    REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token"
    )

    service = build("calendar", "v3", credentials=creds)

    # 🔄 ÇAKIŞMA KONTROLÜ
    conflict_check = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=dt_start.isoformat() + "Z",
        timeMax=dt_end.isoformat() + "Z",
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    if conflict_check.get("items"):
        return {"error": f"{dt_start.strftime('%d %B %Y %H:%M')} saatinde başka bir randevu var."}

    # Randevu oluştur
    event = {
        "summary": f"{customer} – Randevu",
        "description": msg,
        "start": {"dateTime": dt_start.isoformat(), "timeZone": "Europe/Istanbul"},
        "end": {"dateTime": dt_end.isoformat(), "timeZone": "Europe/Istanbul"}
    }

    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return {"status": "success", "event_id": created_event.get("id")}
