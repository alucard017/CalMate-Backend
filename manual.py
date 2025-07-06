from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from dateparser import parse
import logging
import re

from calendar_utils import get_calendar_service, check_availability, book_event
from langgraph_flow import app as langgraph_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class BookingRequest(BaseModel):
    user_input: str 

@app.post("/book")
def book_appointment(request: BookingRequest):
    try:
        user_input = request.user_input
        logger.info(f"User input: {user_input}")
        if "am" not in user_input.lower() and "pm" not in user_input.lower():
            current_hour = datetime.now().hour
            if "today" in user_input.lower() and current_hour >= 12:  
                # If today and after noon --> PM
                user_input += " PM"
            elif "today" in user_input.lower() and current_hour < 12:
                # If today and before noon --> AM
                user_input += " AM"
            else:  # Otherwise be default --> AM
                user_input += " AM"
        
        state = {"input_text": user_input}
        
        output = langgraph_app.invoke(state)
        extracted_time = output.get("extracted_time", "")

        if extracted_time == "unknown":
            raise HTTPException(status_code=400, detail="Could not extract a valid date/time.")

        logger.info(f"Extracted time from LangGraph: {extracted_time}")

        cleaned_time = re.sub(r"\bat\b", "", extracted_time).strip()
        start_time = parse(cleaned_time)

        if not start_time:
            raise HTTPException(status_code=400, detail="Invalid or unparseable datetime.")

        logger.info(f"Parsed start time using dateparser: {start_time}")

        # Calculate the end time --> after 30 minutes
        end_time = start_time + timedelta(minutes=30)
        service = get_calendar_service()

        if not check_availability(start_time, end_time, service):
            raise HTTPException(status_code=409, detail="Time slot is already booked.")

        logger.info(f"Availability checked for {start_time} to {end_time}: Available")

        link = book_event("CalMate Booking", start_time, end_time, service)
        logger.info(f"Event created with link: {link}")

        return {"status": "success", "calendar_link": link}

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
