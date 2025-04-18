from fastapi import FastAPI
from pydantic import BaseModel
import re
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os

app = FastAPI()

# Ortam değişkenleri (Render'a elle girmen gerekiyor)
CALENDAR_ID = os.getenv("CALENDAR_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")

class EventRequest(BaseModel):
    message: str

@app.post("/add-event")
def add_event(data: EventRequest):
    msg = data.message

    # Mesajdan tarih, saat ve müşteri adını ayıklama
    date_match = re.search(r"(\d{1,2} [A-Za-zçğıöşüÇĞİÖŞÜ]+ \d{4})", msg)
    time_match = re.search(r"saat (\d{1,2}):?(\d{2})?", msg)
    customer_match = re.search(r"^(.*?) müşterisinin", msg)

    if not (date_match and time_match and customer_match):
        return {"error": "Tarih, saat veya müşteri adı anlaşılamadı."}

    date_str = date_match.group(1)
    hour = int(time_match.group(1))
    minute = int(time_match.group(2)) if time_match.group(2) else 0
    customer = customer_match.group(1)

    # Türkçe ayları İngilizce'ye çevir
    aylar = {
        "Ocak": "January", "Şubat": "February", "Mart": "March", "Nisan": "April",
        "Mayıs": "May", "Haziran": "June", "Temmuz": "July", "Ağustos": "August",
        "Eylül": "September", "Ekim": "October", "Kasım": "November", "Aralık": "December"
    }
    for tr, en in aylar.items():
        if tr in date_str:
            date_str = date_str.replace(tr, en)
            break

    try:
        dt_start = datetime.strptime(date_str, "%d %B %Y")
    except ValueError:
        return {"error": "Tarih formatı çözülemedi."}

    dt_start = dt_start.replace(hour=hour, minute=minute)
    dt_end = dt_start + timedelta(hours=1)

    try:
        creds = Credentials(
            token=None,
            refresh_token=REFRESH_TOKEN,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token"
        )

        service = build("calendar", "v3", credentials=creds)

        event = {
            "summary": f"{customer} – Randevu",
            "description": msg,
            "start": {
                "dateTime": dt_start.isoformat(),
                "timeZone": "Europe/Istanbul",
            },
            "end": {
                "dateTime": dt_end.isoformat(),
                "timeZone": "Europe/Istanbul",
            },
        }

        created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return {"status": "success", "event_id": created_event.get("id")}

    except Exception as e:
        return {"error": str(e)}
