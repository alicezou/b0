import datetime
import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

def get_time():
    """Get the current local time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def read_profile(user_id: str, workspace: str = "."):
    """Read the user's personal profile file."""
    filename = f"USER-{user_id}.md" if user_id else "USER.md"
    path = Path(workspace) / filename
    if not path.exists():
        return f"Profile file {filename} not found."
    return path.read_text()

def write_profile(user_id: str, content: str, workspace: str = "."):
    """Write or update the user's personal profile file."""
    filename = f"USER-{user_id}.md" if user_id else "USER.md"
    path = Path(workspace) / filename
    path.write_text(content)
    logger.info(f"User profile updated: {filename}")
    return f"Successfully updated profile file: {filename}"

def read_global_memory(workspace: str = "."):
    """Read the global memory file shared across all users."""
    path = Path(workspace) / "MEMORY.md"
    if not path.exists():
        return "Global memory file not found."
    return path.read_text()

def write_global_memory(content: str, workspace: str = "."):
    """Write or update the global memory file shared across all users."""
    path = Path(workspace) / "MEMORY.md"
    path.write_text(content)
    logger.info("Global memory (MEMORY.md) updated")
    return "Successfully updated global memory."

def get_weather(location: str):
    """Get the current weather for a given location."""
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
        geo_res = requests.get(geo_url)
        geo_res.raise_for_status()
        geo_data = geo_res.json()
        
        if not geo_data.get("results"):
            return f"Could not find location: {location}"
        
        result = geo_data["results"][0]
        lat, lon = result["latitude"], result["longitude"]
        name, country = result.get("name", location), result.get("country", "")
        
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        weather_res = requests.get(weather_url)
        weather_res.raise_for_status()
        weather_data = weather_res.json()
        
        current = weather_data.get("current_weather")
        if not current:
            return f"Could not get weather data for {name}."
        
        desc = {
            0: "Clear sky",
            1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Depositing rime fog",
            51: "Drizzle: Light", 53: "Drizzle: Moderate", 55: "Drizzle: Dense intensity",
            61: "Rain: Slight", 63: "Rain: Moderate", 65: "Rain: Heavy intensity",
            71: "Snow fall: Slight", 73: "Snow fall: Moderate", 75: "Snow fall: Heavy intensity",
            80: "Rain showers: Slight", 81: "Rain showers: Moderate", 82: "Rain showers: Violent",
            95: "Thunderstorm: Slight or moderate",
        }.get(current.get("weathercode"), "Unknown")
        
        return (f"Current weather in {name}, {country}:\n"
                f"- Temperature: {current.get('temperature')}°C\n"
                f"- Condition: {desc}\n"
                f"- Wind Speed: {current.get('windspeed')} km/h")
        
    except Exception as e:
        logger.error(f"Error fetching weather: {e}")
        return f"Error fetching weather: {str(e)}"

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
            "name": "read_profile",
            "description": "Read the personal profile (identity, preferences) of the current user",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_profile",
            "description": "Update or save new personal facts/preferences to the current user's profile",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The full new content for the profile file"}
                },
                "required": ["content"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_global_memory",
            "description": "Read the global memory file which contains information shared across all users and bots.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_global_memory",
            "description": "Update or save new facts to the global memory file shared across all users and bots.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The full new content for the global memory file"}
                },
                "required": ["content"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a specific city or location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "The city and country, e.g. 'San Francisco, CA' or 'Tokyo'"}
                },
                "required": ["location"]
            },
        },
    }
]

# Map names to functions for execution
TOOL_MAP = {
    "get_time": get_time,
    "read_profile": read_profile,
    "write_profile": write_profile,
    "read_global_memory": read_global_memory,
    "write_global_memory": write_global_memory,
    "get_weather": get_weather,
}
