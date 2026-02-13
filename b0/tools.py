import datetime
from pathlib import Path

def get_time():
    """Get the current local time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def read_user_memory(user_id: str, caller_id: str = None, workspace: str = "."):
    """Read the user's personal profile/memory file."""
    if caller_id and user_id != caller_id:
        return f"Permission denied: You cannot read memory for user {user_id}."
    
    path = Path(workspace) / f"USER-{user_id}.md"
    if not path.exists():
        return f"Memory file for user {user_id} not found."
    return path.read_text()

def write_user_memory(user_id: str, content: str, caller_id: str = None, workspace: str = "."):
    """Write or update the user's personal profile/memory file."""
    if caller_id and user_id != caller_id:
        return f"Permission denied: You cannot write memory for user {user_id}."
    
    path = Path(workspace) / f"USER-{user_id}.md"
    path.write_text(content)
    return f"Successfully updated memory for user {user_id}."

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
    },
    {
        "type": "function",
        "function": {
            "name": "read_user_memory",
            "description": "Read the personal profile and facts about the user",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The Telegram user ID"}
                },
                "required": ["user_id"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_user_memory",
            "description": "Update or save new facts to the user's personal profile",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "The Telegram user ID"},
                    "content": {"type": "string", "description": "The full new content for the memory file"}
                },
                "required": ["user_id", "content"]
            },
        },
    }
]

# Map names to functions for execution
TOOL_MAP = {
    "get_time": get_time,
    "read_user_memory": read_user_memory,
    "write_user_memory": write_user_memory,
}
