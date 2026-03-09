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
    
    # Copy templates if workspace is empty
    if not any(path.iterdir()):
        template_dir = resources.files("b0.templates")
        for template_file in template_dir.iterdir():
            if template_file.is_file() and template_file.name != "USER.md":
                dest = path / template_file.name
                with template_file.open("rb") as f_src, open(dest, "wb") as f_dst:
                    shutil.copyfileobj(f_src, f_dst)
    
    # Ensure RUNTIME-MEMORY.md exists so MEMORY.md remains untouched
    # This runs every time to ensure the program has a mutable memory file
    # It is located in the current execution directory
    runtime_memory = Path("RUNTIME-MEMORY.md")
    base_memory = path / "MEMORY.md"
    if base_memory.exists() and not runtime_memory.exists():
        shutil.copy2(base_memory, runtime_memory)
        logging.info(f"Generated {runtime_memory} from {base_memory}")


@app.command()
def telegram(workspace: str = typer.Option(".", help="Workspace directory for templates")):
    setup_workspace(workspace)
    from .telegram import run_bot
    run_bot(workspace)

def main():
    app()
