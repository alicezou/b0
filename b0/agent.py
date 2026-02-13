import copy
import os
from pathlib import Path
from . import llm

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
                self.messages.append({"role": "system", "content": path.read_text()})

    def fork(self, purpose: str = ""):
        child = Agent(workspace=str(self.workspace), messages=copy.deepcopy(self.messages), parent=self, purpose=purpose)
        self.children.append(child)
        return child

    async def chat(self, prompt: str):
        self.messages.append({"role": "user", "content": prompt})
        answer = await llm.complete(self.messages)
        self.messages.append({"role": "assistant", "content": answer})
        return answer

    async def run(self):
        """Interactive loop managed by the agent."""
        import typer
        while True:
            prompt = typer.prompt("You")
            if prompt.lower() in ["exit", "quit"]:
                break
            answer = await self.chat(prompt)
            typer.echo(f"AI: {answer}")
