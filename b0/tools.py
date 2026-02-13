import datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def get_time():
    """Get the current local time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def read_user_memory(user_id: str = None, caller_id: str = None, workspace: str = "."):
    """Read the user's personal profile/memory file."""
    if caller_id and user_id != caller_id:
        return f"Permission denied: You cannot read memory for user {user_id}."
    
    filename = f"USER-{user_id}.md" if user_id else "USER.md"
    path = Path(workspace) / filename
    if not path.exists():
        return f"Memory file {filename} not found."
    return path.read_text()

def write_user_memory(user_id: str = None, content: str = None, caller_id: str = None, workspace: str = "."):
    """Write or update the user's personal profile/memory file."""
    if caller_id and user_id != caller_id:
        return f"Permission denied: You cannot write memory for user {user_id}."
    
    filename = f"USER-{user_id}.md" if user_id else "USER.md"
    path = Path(workspace) / filename
    path.write_text(content)
    logger.info(f"User memory updated: {filename}")
    return f"Successfully updated memory file: {filename}"

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
            "description": "Read your personal profile and facts about the current user",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_user_memory",
            "description": "Update or save new facts to the current user's personal profile",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The full new content for the memory file"}
                },
                "required": ["content"]
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
