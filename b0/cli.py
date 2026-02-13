import typer
import asyncio
import os
import shutil
import logging
from pathlib import Path
from importlib import resources
from .agent import Agent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = typer.Typer()

def setup_workspace(workspace_path: str):
    path = Path(workspace_path)
    if not path.exists():
        path.mkdir(parents=True)
    
    if not any(path.iterdir()):
        template_dir = resources.files("b0.templates")
        for template_file in template_dir.iterdir():
            if template_file.is_file() and template_file.name != "USER.md":
                dest = path / template_file.name
                with template_file.open("rb") as f_src, open(dest, "wb") as f_dst:
                    shutil.copyfileobj(f_src, f_dst)

@app.command()
def chat(workspace: str = typer.Option(".", help="Workspace directory for templates")):
    setup_workspace(workspace)
    agent = Agent(workspace=workspace)
    asyncio.run(agent.run())

@app.command()
def telegram(workspace: str = typer.Option(".", help="Workspace directory for templates")):
    setup_workspace(workspace)
    from .telegram import run_bot
    run_bot(workspace)

def main():
    app()
