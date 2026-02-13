import copy
import os
import logging
import json
from pathlib import Path
from . import llm
from .tools import TOOLS, TOOL_MAP

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, workspace: str = ".", messages=None, parent=None, purpose: str = ""):
        self.workspace = Path(workspace)
        self.parent = parent
        self.purpose = purpose
        self.children = []
        self.messages = messages or []
        
        if not self.messages:
            self._init_context()

    def _init_context(self):
        """Loads SOUL and AGENT templates as system prompts if they exist."""
        for name in ["SOUL.md", "AGENT.md"]:
            path = self.workspace / name
            if path.exists():
                logger.info(f"Loading system prompt from {path}")
                self.messages.append({"role": "system", "content": path.read_text()})

    def fork(self, purpose: str = ""):
        child = Agent(workspace=str(self.workspace), messages=copy.deepcopy(self.messages), parent=self, purpose=purpose)
        self.children.append(child)
        return child

    async def chat(self, prompt: str):
        self.messages.append({"role": "user", "content": prompt})
        
        while True:
            message = await llm.complete(self.messages, tools=TOOLS)
            if not message:
                return "Error: LLM failed to respond."
            
            self.messages.append(message)
            
            if not message.tool_calls:
                return message.content

            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                logger.info(f"Executing tool: {fn_name}({fn_args})")
                
                if fn_name in TOOL_MAP:
                    result = TOOL_MAP[fn_name](**fn_args)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": fn_name,
                        "content": str(result)
                    })
                else:
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": fn_name,
                        "content": f"Error: Tool {fn_name} not found."
                    })

    async def run(self):
        """Interactive loop managed by the agent."""
        import typer
        while True:
            prompt = typer.prompt("You")
            if prompt.lower() in ["exit", "quit"]:
                break
            answer = await self.chat(prompt)
            typer.echo(f"AI: {answer}")
