from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
from dateparser.search import search_dates
import pytz
from datetime import datetime
from dateparser import parse


class GraphState(TypedDict):
    input_text: Annotated[str, "User's message"]
    extracted_time: Annotated[str, "Extracted time string"]

def extract_time_node(state: GraphState) -> GraphState:
    text = str(parse(state['input_text']))
    result = search_dates(text, settings={'PREFER_DATES_FROM': 'future'})

    if result:
        dt = result[0][1]
        print(dt);
        if "AM" in dt.strftime("%p") or "PM" in dt.strftime("%p"):
            ist = pytz.timezone("Asia/Kolkata")
            dt = dt.astimezone(ist)
            extracted = dt.strftime("%Y-%m-%d at %I:%M %p")
        else:
            extracted = "unknown"
    else:
        extracted = "unknown"  # If no time is extracted -> mark as unknown

    return {**state, "extracted_time": extracted}

def print_node(state: GraphState) -> GraphState:
    print("Extracted time:", state["extracted_time"])
    return state

graph = StateGraph(GraphState)
graph.add_node("extract_time", extract_time_node)
graph.add_node("print", print_node)

graph.set_entry_point("extract_time")
graph.add_edge("extract_time", "print")
graph.add_edge("print", END)

app = graph.compile()

# Manual test
if __name__ == "__main__":
    result = app.invoke({"input_text": "Schedule a call tomorrow at 3 PM"})
    print(result)
