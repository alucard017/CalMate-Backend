from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
from calender_oauth import get_calendar_service, book_event, check_availability
import dateparser
import pytz
import os
import json
import pickle
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]
REDIRECT_URI = "http://localhost:8000/auth/google/callback"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

class CheckAvailabilityRequest(BaseModel):
    user_email: str
    start_time: str
    end_time: str

class BookEventRequest(BaseModel):
    user_email: str
    summary: str
    start_time: str
    end_time: str
    attendees: list[str] = []

class FindOpenSlotsRequest(BaseModel):
    user_email: str
    date: str
    duration_minutes: int

class ChatRequest(BaseModel):
    messages: list

def parse_date(text: str):
    return dateparser.parse(text, settings={
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": datetime.now()
    })

@app.get("/auth/google")
def auth_google():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(prompt="consent", include_granted_scopes="true")
    return RedirectResponse(auth_url)

@app.get("/auth/google/callback")
def auth_google_callback(request: Request):
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        request_url = str(request.url)
        flow.fetch_token(authorization_response=request_url)
        credentials = flow.credentials

        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        user_email = user_info['email']

        os.makedirs("tokens", exist_ok=True)
        with open(f"tokens/{user_email}.pickle", "wb") as f:
            pickle.dump(credentials, f)

        return RedirectResponse(f"http://localhost:8501/?user={user_email}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth callback error: {str(e)}")

@app.post("/check-availability")
def check_avail(req: CheckAvailabilityRequest):
    try:
        service = get_calendar_service(req.user_email)
        start_dt = parse_date(req.start_time)
        end_dt = parse_date(req.end_time)

        if not start_dt or not end_dt:
            raise ValueError("Invalid datetime format")
        return {"available": check_availability(start_dt, end_dt, service)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/book-event")
def book_event_endpoint(req: BookEventRequest):
    try:
        service = get_calendar_service(req.user_email)
        start_dt = parse_date(req.start_time)
        end_dt = parse_date(req.end_time)

        if not start_dt or not end_dt:
            raise ValueError("Invalid datetime format")
        return {
            "calendar_link": book_event(
                summary=req.summary,
                start_time=start_dt,
                end_time=end_dt,
                attendees=req.attendees,
                service=service
            )
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/find-open-slots")
def find_slots(req: FindOpenSlotsRequest):
    try:
        service = get_calendar_service(req.user_email)
        ist = pytz.timezone("Asia/Kolkata")
        start_hour, end_hour = 9, 19

        date_obj = parse_date(req.date)
        if not date_obj:
            raise ValueError("Invalid date input")

        date_obj = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)

        slots = []
        for hour in range(start_hour, end_hour):
            start = date_obj + timedelta(hours=hour)
            end = start + timedelta(minutes=req.duration_minutes)

            if start.tzinfo is None:
                start = ist.localize(start)
            if end.tzinfo is None:
                end = ist.localize(end)

            if check_availability(start, end, service):
                slots.append({
                    "start_time": start.isoformat(),
                    "end_time": end.isoformat()
                })

        return {"open_slots": slots}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
def chat_with_llm(req: ChatRequest):
    try:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "findOpenSlots",
                    "description": "Find available time slots for a given date and duration.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_email": {"type": "string"},
                            "date": {"type": "string"},
                            "duration_minutes": {"type": "integer"}
                        },
                        "required": ["user_email", "date", "duration_minutes"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "checkAvailability",
                    "description": "Check if a specific time range is available.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_email": {"type": "string"},
                            "start_time": {"type": "string"},
                            "end_time": {"type": "string"}
                        },
                        "required": ["user_email", "start_time", "end_time"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "bookEvent",
                    "description": "Book an event in the user's calendar and invite people.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_email": {"type": "string"},
                            "summary": {"type": "string"},
                            "start_time": {"type": "string"},
                            "end_time": {"type": "string"},
                            "attendees": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Email addresses of attendees"
                            }
                        },
                        "required": ["user_email", "summary", "start_time", "end_time"]
                    }
                }
            }
        ]

        full_messages = [
            {
                "role": "system",
                "content": (
                    "You are CalMate, a friendly and helpful AI assistant for managing Google Calendar meetings.\n"
                    "You respond casually to greetings, jokes, or small talk, and only use tools when users want to book, check, or find calendar events.\n"
                    "Be friendly, warm, and helpful."
                )
            },
            *req.messages
        ]

        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "http://localhost:8501",
                "X-Title": "CalMate"
            },
            model="openai/gpt-3.5-turbo-0613",
            messages=full_messages,
            tools=tools,
            tool_choice="auto"
        )

        message = response.choices[0].message

        if hasattr(message, "tool_calls") and message.tool_calls:
            full_messages.append({
                "role": "assistant",
                "tool_calls": message.tool_calls,
                "content": None
            })

            for tool_call in message.tool_calls:
                func = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                if func == "findOpenSlots":
                    r = find_slots(FindOpenSlotsRequest(**args))
                elif func == "checkAvailability":
                    r = check_avail(CheckAvailabilityRequest(**args))
                elif func == "bookEvent":
                    r = book_event_endpoint(BookEventRequest(**args))
                else:
                    r = {"error": f"Unknown function {func}"}

                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(r)
                })

            followup = client.chat.completions.create(
                model="openai/gpt-3.5-turbo-0613",
                messages=full_messages
            )
            return {"response": followup.choices[0].message.content.strip()}
        else:
            return {"response": message.content.strip()}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
