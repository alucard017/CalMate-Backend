from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime
import pytz
import os
import pickle

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service(user_email: str):
    token_path = f"tokens/{user_email}.pickle"
    creds = None

    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
        creds = flow.run_local_server(port=8000)

        os.makedirs("tokens", exist_ok=True)
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    return build('calendar', 'v3', credentials=creds)


def localize_if_needed(dt: datetime, tz):
    if dt.tzinfo is None:
        return tz.localize(dt)
    return dt.astimezone(tz)

def check_availability(start_time: datetime, end_time: datetime, service) -> bool:
    ist = pytz.timezone("Asia/Kolkata")
    start_time = localize_if_needed(start_time, ist)
    end_time = localize_if_needed(end_time, ist)

    events_result = service.events().list(
        calendarId='primary',
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    return len(events) == 0

def book_event(summary: str, start_time: datetime, end_time: datetime, attendees: list, service) -> str:
    ist = pytz.timezone("Asia/Kolkata")
    start_time = localize_if_needed(start_time, ist)
    end_time = localize_if_needed(end_time, ist)

    event = {
        'summary': summary,
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Asia/Kolkata'},
        'attendees': [{'email': email} for email in attendees],
        'conferenceData': {
            'createRequest': {
                'conferenceSolutionKey': {
                    'type': 'hangoutsMeet'
                },
                'requestId': f"{start_time.timestamp()}"  # unique ID
            }
        },
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 30},
                {'method': 'popup', 'minutes': 10}
            ]
        }
    }

    created_event = service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1,  # Required for Meet
        sendUpdates='all'
    ).execute()

    return created_event.get('htmlLink')
