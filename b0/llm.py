import litellm
import requests
import logging
from . import config

logger = logging.getLogger(__name__)

litellm.set_verbose = False
litellm.suppress_debug_info = True

class LLMConnector:
    def __init__(self):
        self._model = None

    @property
    def model(self):
        if config.DEFAULT_LLM_MODEL:
            logger.info(f"Using hardcoded model: {config.DEFAULT_LLM_MODEL}")
            return config.DEFAULT_LLM_MODEL
        if not self._model:
            self._model = self._find_model()
            logger.info(f"Discovery: using model {self._model}")
        return self._model

    def _find_model(self):
        base = config.OLLAMA_API_BASE or "http://localhost:11434"
        try:
            resp = requests.get(f"{base}/api/tags", timeout=1)
            if resp.status_code == 200:
                models = [f"ollama/{x['name']}" for x in resp.json().get('models', [])]
                if models: 
                    logger.info(f"Ollama models found: {models}")
                    return models[0]
        except Exception as e:
            logger.debug(f"Ollama discovery failed: {e}")
        
        logger.info("No local models found, falling back to gpt-4o")
        return "gpt-4o"

    async def complete(self, messages: list, model: str = None, tools: list = None):
        m = model or self.model
        
        if config.OPENAI_API_BASE and "openrouter.ai" in config.OPENAI_API_BASE:
            if not m.startswith("openrouter/"):
                m = f"openrouter/{m}"
        
        kwargs = {
            "model": m,
            "messages": messages,
        }
        
        if tools:
            kwargs["tools"] = tools
        
        if config.OPENAI_API_KEY:
            kwargs["api_key"] = config.OPENAI_API_KEY
        if config.OPENAI_API_BASE:
            kwargs["api_base"] = config.OPENAI_API_BASE
            
        if m.startswith("ollama/"):
            kwargs["api_base"] = config.OLLAMA_API_BASE or "http://localhost:11434"

        try:
            response = await litellm.acompletion(**kwargs)
            return response.choices[0].message
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return None

client = LLMConnector()
complete = client.complete
