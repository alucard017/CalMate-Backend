from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import pytz
import os
import json

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Your calendar ID
CALENDAR_ID = 'apurbasundar2002@gmail.com'

def get_calendar_service():
    """
    Authenticates using service account JSON stored in environment variable.
    Returns Google Calendar service client.
    """
    # Load credentials from the environment variable
    service_account_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES
    )
    service = build('calendar', 'v3', credentials=credentials)
    return service


def check_availability(start_time: datetime, end_time: datetime, service) -> bool:
    """
    Checks if a given time slot is available.
    """
    # Ensure time is timezone-aware (Asia/Kolkata)
    ist = pytz.timezone("Asia/Kolkata")
    start_time = ist.localize(start_time)
    end_time = ist.localize(end_time)

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    return len(events) == 0  # Return True if slot is available

def book_event(summary: str, start_time: datetime, end_time: datetime, service) -> str:
    """
    Books a new event on the calendar if the slot is free.
    Returns the calendar event link.
    """
    event = {
        'summary': summary,
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
    }

    created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created_event.get('htmlLink')
