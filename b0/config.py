import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL")
