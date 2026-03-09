import logging
import copy
import json
from pathlib import Path
from importlib import resources
from . import llm
from .tools import TOOLS, TOOL_MAP

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, workspace: str = ".", messages=None, parent=None, purpose: str = "", user_id: str = None):
        self.workspace = Path(workspace)
        self.parent = parent
        self.purpose = purpose
        self.user_id = user_id
        self.children = []
        self.messages = messages or []
        self.detected_lang = None
        
        if not self.messages:
            self._init_context()
        elif parent:
            self.detected_lang = getattr(parent, 'detected_lang', None)

    def _init_context(self):
        """Loads workspace templates as system prompts if they exist."""
        template_names = ["SOUL.md", "AGENT.md", "TOOLS.md", "RUNTIME-MEMORY.md"]
        
        # Determine the user file name
        user_file = f"USER-{self.user_id}.md" if self.user_id else "USER.md"
        
        # If user-specific file doesn't exist but we have a user_id, create it from template
        user_path = self.workspace / user_file
        if self.user_id and not user_path.exists():
            template_content = resources.files("b0.templates").joinpath("USER.md").read_text()
            user_path.write_text(template_content)
            logger.info(f"Created new user profile: {user_path.absolute()}")

        template_names.append(user_file)

        detected_lang = None
        for name in template_names:
            # RUNTIME-MEMORY.md is in the current dir; others are in workspace
            if name == "RUNTIME-MEMORY.md":
                path = Path(name)
            else:
                path = self.workspace / name
            
            if path.exists():
                content = path.read_text()
                logger.info(f"Loading system prompt from {path} (length: {len(content)})")
                if "Preferred Language" in content:
                    import re
                    # Match "Preferred Language" inside bold markers, then capture value on the same line (allowing empty)
                    # This specifically looks for: **Preferred Language:** [value]
                    lang = re.search(r"\*\*Preferred Language[:]?\*\*[:]?[ \t]*([^\n\*]*)", content)
                    if lang and lang.group(1).strip():
                        self.detected_lang = lang.group(1).strip()
                        logger.info(f"Detected language preference in {path.name}: '{self.detected_lang}'")
                self.messages.append({"role": "system", "content": content})

    def fork(self, purpose: str = ""):
        child = Agent(workspace=str(self.workspace), messages=copy.deepcopy(self.messages), parent=self, purpose=purpose, user_id=self.user_id)
        child.detected_lang = self.detected_lang
        self.children.append(child)
        return child

    async def chat(self, content: str | list):
        self.messages.append({"role": "user", "content": content})
        
        while True:
            # Dynamically inject language reinforcement as the last system message
            # this ensures it remains high-priority even if other system prompts are added
            llm_messages = self.messages[:]
            if self.detected_lang:
                llm_messages.append({
                    "role": "system", 
                    "content": f"IMPORTANT: Your response language MUST be {self.detected_lang}. All communication, analysis, and feedback must use this language strictly."
                })
            
            message = await llm.complete(llm_messages, tools=TOOLS)
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
                    # Inject context if the tool supports it
                    if fn_name in ["read_profile", "write_profile", "schedule_reminder", "get_reminders", "log_intake", "get_daily_intake", "update_profile_field"]:
                        fn_args["user_id"] = self.user_id
                        fn_args["workspace"] = str(self.workspace)
                    
                    if fn_name in ["read_global_memory", "write_global_memory"]:
                        fn_args["workspace"] = str(self.workspace)
                    
                    result = TOOL_MAP[fn_name](**fn_args)
                    
                    # Update local language preference if modified via tool
                    if fn_name == "update_profile_field" and fn_args.get("field_name") == "Preferred Language":
                        self.detected_lang = fn_args.get("new_value")
                        logger.info(f"Agent state updated: language preference is now '{self.detected_lang}'")
                    elif fn_name == "write_profile":
                        # Attempt to re-extract language from full profile content
                        import re
                        lang_match = re.search(r"\*\*Preferred Language[:]?\*\*[:]?[ \t]*([^\n\*]*)", fn_args.get("content", ""))
                        if lang_match and lang_match.group(1).strip():
                            self.detected_lang = lang_match.group(1).strip()
                            logger.info(f"Agent state updated via write_profile: language is now '{self.detected_lang}'")

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
