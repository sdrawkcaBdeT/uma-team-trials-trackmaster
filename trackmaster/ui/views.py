# trackmaster/ui/views.py

import discord
import asyncio
from typing import List, Dict, Any

from trackmaster.bot import TrackmasterBot
from .modals import ScoreEditModal

class ValidationView(discord.ui.View):
    """
    A view with Confirm, Edit, and Cancel buttons for validating an OCR run.
    """
    def __init__(self, bot: TrackmasterBot, event_id: str, corrected_data: List[Dict[str, Any]]):
        super().__init__(timeout=300) # 5 minute timeout
        self.bot = bot
        self.event_id = event_id
        self.corrected_data = corrected_data
        self.interaction: discord.Interaction = None # To store the original interaction

    async def on_timeout(self):
        # This runs if the user doesn't click anything for 5 minutes
        if self.interaction:
            await self.interaction.edit_original_response(content="This submission timed out. Please run /submit again.", view=None, embed=None)
            # We can't use to_thread here, so we'll create a task
            asyncio.create_task(
                asyncio.to_thread(self.bot.db_manager.set_run_status, self.event_id, 'rejected')
            )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm_run")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Defer to show "thinking"
        await interaction.response.defer()
        
        # 2. Update database
        success = await asyncio.to_thread(
            self.bot.db_manager.set_run_status, self.event_id, 'approved'
        )
        
        # 3. Disable buttons and give feedback
        if success:
            await interaction.edit_original_response(content=f"✅ **{self.event_id}** approved and saved!", view=None, embed=None)
        else:
            await interaction.edit_original_response(content=f"❌ Error saving to database. Please try again.", view=None, embed=None)
        
        self.stop() # Stop the view from listening

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.blurple, custom_id="edit_run")
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Pop up the Modal
        # We pass the event_id so the modal knows what run to edit
        modal = ScoreEditModal(bot=self.bot, event_id=self.event_id)
        await interaction.response.send_modal(modal)

        # Note: The original message (with the Confirm button) remains.
        # The modal will send its own response when submitted.

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel_run")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Defer
        await interaction.response.defer()
        
        # 2. Update database (delete the run)
        success = await asyncio.to_thread(
            self.bot.db_manager.set_run_status, self.event_id, 'rejected' # 'rejected' tells our DB logic to DELETE
        )

        # 3. Disable buttons and give feedback
        if success:
            await interaction.edit_original_response(content=f"🗑️ Run **{self.event_id}** has been cancelled and deleted.", view=None, embed=None)
        else:
            await interaction.edit_original_response(content=f"❌ Error deleting from database. Please try again.", view=None, embed=None)
        
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures only the original user can click the buttons."""
        if self.interaction is None:
            self.interaction = interaction # Store the first interaction
            
        if interaction.user.id != self.interaction.user.id:
            await interaction.response.send_message("You are not the author of this submission.", ephemeral=True)
            return False
        return True