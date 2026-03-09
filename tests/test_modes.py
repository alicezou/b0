import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import json
import os
import sys

# Ensure b0 is importable
sys.path.append(os.getcwd())

from b0 import telegram, agent, auth, tools

class TestBotModes(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Clear global state in telegram module
        telegram.user_agents.clear()
        telegram.user_modes.clear()
        telegram.user_buffers.clear()
        
        # Setup temp workspace
        self.workspace = Path("/tmp/b0_test")
        if self.workspace.exists():
            import shutil
            shutil.rmtree(self.workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Create necessary templates
        (self.workspace / "SOUL.md").write_text("# Soul\nWelcome.")
        (self.workspace / "AGENT.md").write_text("# Agent\nGuidelines.")
        (self.workspace / "TOOLS.md").write_text("# Tools\nAvailable tools.")
        (self.workspace / "MEMORY.md").write_text("# Memory\nEmpty memory.")
        (self.workspace / "COACH.md").write_text("# Coach Personality\nBe strict.")
        (self.workspace / "USER.md").write_text("# User Profile Template\nNo info.")

        self.mock_context = MagicMock()
        self.mock_context.bot_data = {
            "workspace": "/tmp/b0_test",
            "auth_manager": MagicMock()
        }
        self.mock_context.job_queue = MagicMock()
        self.mock_context.bot = AsyncMock()

        self.mock_update = MagicMock()
        self.mock_update.effective_user.id = 123456
        self.mock_update.effective_user.username = "testuser"
        self.mock_update.effective_chat.id = 999999
        self.mock_update.message = AsyncMock()
        self.mock_update.message.photo = None

    async def test_normal_mode_behavior(self):
        """Test that normal mode provides a neutral response."""
        ident = "testuser-token"
        self.mock_context.bot_data["auth_manager"].get_identifier.return_value = ident
        self.mock_context.bot_data["auth_manager"].is_authorized.return_value = True
        
        self.mock_update.message.text = "Hello!"
        
        with patch("b0.llm.complete", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock(content="Hello! How can I help?", tool_calls=None)
            
            await telegram.handle_message(self.mock_update, self.mock_context)
            
            # Use .get() to avoid KeyError if not explicitly initialized to 'normal'
            mode = telegram.user_modes.get(ident, "normal") 
            self.assertEqual(mode, "normal")
            self.mock_context.bot.send_message.assert_called()

    async def test_transition_to_coach_mode(self):
        """Test that /coach command triggers pending goal state if profile is missing."""
        ident = "testuser-token"
        self.mock_context.bot_data["auth_manager"].get_identifier.return_value = ident
        self.mock_context.bot_data["auth_manager"].is_authorized.return_value = True
        
        # Ensure profile is missing stats
        profile_path = self.workspace / f"USER-{ident}.md"
        profile_path.write_text("## My Bodybuilding Profile & Goals:\n* **Current Stats:** \n* **Goal:** \n")
        
        await telegram.coach(self.mock_update, self.mock_context)
        
        self.assertEqual(telegram.user_modes[ident], "coach_pending_goal")
        self.mock_update.message.reply_text.assert_called()

    async def test_coach_active_intake_logging(self):
        """Test that coach mode logs intake when analyzing a meal."""
        ident = "testuser-token"
        self.mock_context.bot_data["auth_manager"].get_identifier.return_value = ident
        self.mock_context.bot_data["auth_manager"].is_authorized.return_value = True
        telegram.user_modes[ident] = "coach"
        
        # Initialize coach agent
        coach_agent = agent.Agent(workspace="/tmp/b0_test", purpose="Coach Test", user_id=ident)
        telegram.user_agents[ident] = coach_agent
        
        self.mock_update.message.text = "I had a bowl of rice and chicken."
        
        # Tool call for logging intake
        tool_call = MagicMock()
        tool_call.id = "intake_1"
        tool_call.function.name = "log_intake"
        tool_call.function.arguments = json.dumps({
            "meal_description": "rice and chicken",
            "calories": 500,
            "protein": 30,
            "carbs": 50,
            "fats": 10
        })
        
        tool_msg = MagicMock(content="Logging.")
        tool_msg.tool_calls = [tool_call]
        
        final_msg = MagicMock(content="Verdict: Good. Improvement: More veggies.", tool_calls=None)
        
        with patch("b0.llm.complete", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = [tool_msg, final_msg]
            
            await telegram.handle_message(self.mock_update, self.mock_context)
            
            # Verify intake file exists in the fake workspace
            intake_path = self.workspace / f"INTAKE-{ident}.json"
            self.assertTrue(intake_path.exists())
            
            intake_content = json.loads(intake_path.read_text())
            self.assertEqual(len(intake_content), 1)
            self.assertEqual(intake_content[0]["meal"], "rice and chicken")
            self.assertEqual(intake_content[0]["calories"], 500)

if __name__ == '__main__':
    unittest.main()
