import litellm
import requests
from . import config

class LLMConnector:
    def __init__(self):
        self._model = None

    @property
    def model(self):
        if config.DEFAULT_LLM_MODEL:
            return config.DEFAULT_LLM_MODEL
        if not self._model:
            self._model = self._find_model()
        return self._model

    def _find_model(self):
        base = config.OLLAMA_API_BASE or "http://localhost:11434"
        try:
            resp = requests.get(f"{base}/api/tags", timeout=1)
            if resp.status_code == 200:
                models = [f"ollama/{x['name']}" for x in resp.json().get('models', [])]
                if models: return models[0]
        except: pass
        return "gpt-4o"

    async def complete(self, messages: list, model: str = None):
        m = model or self.model
        
        # If using OpenRouter and model is not prefixed, prefix it
        if config.OPENAI_API_BASE and "openrouter.ai" in config.OPENAI_API_BASE:
            if not m.startswith("openrouter/"):
                m = f"openrouter/{m}"
        
        kwargs = {
            "model": m,
            "messages": messages,
        }
        
        if config.OPENAI_API_KEY:
            kwargs["api_key"] = config.OPENAI_API_KEY
        if config.OPENAI_API_BASE:
            kwargs["api_base"] = config.OPENAI_API_BASE
            
        if m.startswith("ollama/"):
            kwargs["api_base"] = config.OLLAMA_API_BASE or "http://localhost:11434"

        try:
            response = await litellm.acompletion(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM Error: {str(e)}"

client = LLMConnector()
complete = client.complete
