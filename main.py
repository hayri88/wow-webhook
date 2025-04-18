from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timedelta
import os
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

app = FastAPI()

# Çok basit ay adları listesi (TR ve NL destekli)
MONTHS_TR_NL = {
    "ocak": "January", "şubat": "February", "mart": "March", "nisan": "April",
    "mayıs": "May", "haziran": "June", "temmuz": "July", "ağustos": "August",
    "eylül": "September", "ekim": "October", "kasım": "November", "aralık": "December",
    "januari": "January", "februari": "February", "maart": "March", "april": "April",
    "mei": "May", "juni": "June", "juli": "July", "augustus": "August",
    "september": "September", "oktober": "October", "november": "November", "december": "December"
}

class EventRequest(BaseModel):
    message: str

@app.post("/add-event")
def add_event(data: EventRequest):
    msg = data.message.lower()

    # Tarih: "24 nisan 2025" veya "23 april 2025"
    date_match = None
    for month in MONTHS_TR_NL:
        date_match = re.search(r"(\d{1,2}) " + month + r" (\d{4})", msg)
        if date_match:
            month_en = MONTHS_TR_NL[month]
            break

    time_match = re.search(r"(saat|om)? ?(\d{1,2})[:\.]?(\d{2})", msg)
    name_match = re.search(r"^([a-zçşıöüğâêîûéàëäèïa-z0-9\- ]+?) (müşterisi|müsterisinin|klant|heeft|musterim|klant heeft)", msg)

    if not (date_match and time_match and name_match):
        return {"error": "Tarih, saat veya müşteri adı bulunamadı."}

    try:
        date_str = f"{date_match.group(1)} {month_en} {date_match.group(2)}"
        dt_date = datetime.strptime(date_str, "%d %B %Y")
        hour = int(time_match.group(2))
        minute = int(time_match.group(3))
    except:
        return {"error": "Tarih veya saat formatı geçersiz."}

    customer = name_match.group(1).strip().title()
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

    # Çakışma kontrolü
    conflict_check = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=dt_start.isoformat() + "Z",
        timeMax=dt_end.isoformat() + "Z",
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    if conflict_check.get("items"):
        return {"error": f"{dt_start.strftime('%d %B %Y %H:%M')} saatinde başka bir randevu var."}

    event = {
        "summary": f"{customer} – Randevu",
        "description": data.message,
        "start": {"dateTime": dt_start.isoformat(), "timeZone": "Europe/Istanbul"},
        "end": {"dateTime": dt_end.isoformat(), "timeZone": "Europe/Istanbul"}
    }

    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return {"status": "success", "event_id": created_event.get("id")}

@app.get("/list-events")
def list_events():
    creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/calendar.readonly"])
    service = build("calendar", "v3", credentials=creds)

    now = datetime.utcnow().isoformat() + "Z"
    events_result = service.events().list(
        calendarId=os.getenv("CALENDAR_ID"),
        timeMin=now,
        maxResults=10,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])
    output = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        formatted_date = dt.strftime("%d %B %Y saat %H:%M")
        output.append(f'{event["summary"]} – {formatted_date}')
    return {"events": output}
