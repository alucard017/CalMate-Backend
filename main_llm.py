from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
from calendar_utils import get_calendar_service, check_availability, book_event
import dateparser
import pytz
import os
import json
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

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

class CheckAvailabilityRequest(BaseModel):
    start_time: str
    end_time: str

class BookEventRequest(BaseModel):
    summary: str
    start_time: str
    end_time: str

class FindOpenSlotsRequest(BaseModel):
    date: str
    duration_minutes: int

class ChatRequest(BaseModel):
    messages: list

# Date Parser
def parse_date(text: str):
    return dateparser.parse(text, settings={
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": datetime.now()
    })

@app.post("/check-availability")
def check_avail(req: CheckAvailabilityRequest):
    try:
        service = get_calendar_service()
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
        service = get_calendar_service()
        start_dt = parse_date(req.start_time)
        end_dt = parse_date(req.end_time)

        if not start_dt or not end_dt:
            raise ValueError("Invalid datetime format")
        return {"calendar_link": book_event(req.summary, start_dt, end_dt, service)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/find-open-slots")
def find_slots(req: FindOpenSlotsRequest):
    try:
        service = get_calendar_service()
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
                            "date": {"type": "string"},
                            "duration_minutes": {"type": "integer"}
                        },
                        "required": ["date", "duration_minutes"]
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
                            "start_time": {"type": "string"},
                            "end_time": {"type": "string"}
                        },
                        "required": ["start_time", "end_time"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "bookEvent",
                    "description": "Book an event in the calendar.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "start_time": {"type": "string"},
                            "end_time": {"type": "string"}
                        },
                        "required": ["summary", "start_time", "end_time"]
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
                "HTTP-Referer": "https://calmate-frontend-qn3r.onrender.com/",
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
