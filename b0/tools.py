import datetime

def get_time():
    """Get the current local time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Tool definitions for LiteLLM
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current local time",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    }
]

# Map names to functions for execution
TOOL_MAP = {
    "get_time": get_time,
}
