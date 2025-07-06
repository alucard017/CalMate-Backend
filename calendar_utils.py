from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz
import os

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'apurbasundar2002@gmail.com'
CREDENTIALS_FILE = 'credentials.json'

def get_calendar_service():
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=SCOPES
    )
    service = build('calendar', 'v3', credentials=credentials)
    return service

def localize_if_needed(dt: datetime, tz):
    if dt.tzinfo is None:
        return tz.localize(dt)
    return dt.astimezone(tz)

def check_availability(start_time: datetime, end_time: datetime, service) -> bool:
    ist = pytz.timezone("Asia/Kolkata")
    start_time = localize_if_needed(start_time, ist)
    end_time = localize_if_needed(end_time, ist)

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    return len(events) == 0

def book_event(summary: str, start_time: datetime, end_time: datetime, service) -> str:
    ist = pytz.timezone("Asia/Kolkata")
    start_time = localize_if_needed(start_time, ist)
    end_time = localize_if_needed(end_time, ist)

    event = {
        'summary': summary,
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
    }

    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created_event.get('htmlLink')
