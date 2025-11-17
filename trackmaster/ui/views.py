# trackmaster/ui/views.py

import discord
import asyncio
from typing import List, Dict, Any

from trackmaster.bot import TrackmasterBot
from trackmaster.ui.modals import ScoreEditModal
from trackmaster.ui.embeds import create_confirmation_embed

class ValidationView(discord.ui.View):
    """
    A view with Confirm, Edit, and Cancel buttons for validating an OCR run.
    """
    def __init__(self, bot: TrackmasterBot, event_id: str, corrected_data: List[Dict[str, Any]], original_user_id: int):
        super().__init__(timeout=300) # 5 minute timeout
        self.bot = bot
        self.event_id = event_id
        self.corrected_data = corrected_data
        self.original_user_id = original_user_id # <-- The ID of the person who ran /submit
        self.has_been_actioned = False

    async def disable_all_buttons(self, interaction: discord.Interaction):
        """Disables all buttons, stops the view, and updates the message."""
        self.has_been_actioned = True
        
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        
        # Edit the original message to show the disabled buttons
        try:
            await interaction.edit_original_response(view=self)
        except discord.NotFound:
            pass # Message was already deleted, nothing to do
        
        self.stop() # Stop the view from listening

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm_run")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Defer, but ephemerally so it doesn't say "thinking" publicly
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # 2. Disable buttons *immediately* to prevent race conditions
        await self.disable_all_buttons(interaction)
        
        # 3. Update database
        success = await asyncio.to_thread(
            self.bot.db_manager.set_run_status, self.event_id, 'approved'
        )
        
        # 4. Give NEW feedback
        if success:
            # Create a new "Confirmed" embed
            confirmation_embed = create_confirmation_embed(self.event_id, self.corrected_data)
            
            # Send a new message, since the original was ephemeral
            await interaction.followup.send(embed=confirmation_embed, ephemeral=True)
            
            # Edit the original message (which is ephemeral) to show a final state
            await interaction.edit_original_response(content=f"✅ **{self.event_id}** approved and saved!", embed=None, view=None)
        else:
            await interaction.followup.send("❌ Error saving to database. Please try again.", ephemeral=True)
            await interaction.edit_original_response(content="❌ Error saving to database. Please try again.", embed=None, view=None)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.blurple, custom_id="edit_run")
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # This interaction is NOT deferred, as send_modal handles it
        modal = ScoreEditModal(bot=self.bot, event_id=self.event_id)
        await interaction.response.send_modal(modal)
        # We do not stop the view

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel_run")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Defer, ephemerally
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # 2. Disable buttons *immediately*
        await self.disable_all_buttons(interaction)
        
        # 3. Update database (delete the run)
        success = await asyncio.to_thread(
            self.bot.db_manager.set_run_status, self.event_id, 'rejected'
        )

        # 4. Give feedback
        if success:
            await interaction.followup.send(f"🗑️ Run **{self.event_id}** has been cancelled and deleted.", ephemeral=True)
            await interaction.edit_original_response(content=f"🗑️ Run **{self.event_id}** has been cancelled and deleted.", view=None, embed=None)
        else:
            await interaction.followup.send("❌ Error deleting from database. Please try again.", ephemeral=True)
            await interaction.edit_original_response(content="❌ Error deleting from database. Please try again.", view=None, embed=None)

    async def on_timeout(self):
        # This runs if the user doesn't click anything for 5 minutes
        if not self.has_been_actioned:
            # We don't have the original interaction object, so we can't edit it.
            # But the view is stopped, so the buttons won't work anyway.
            # We will run the DB delete to prevent a pending run from sitting forever.
            await asyncio.to_thread(self.bot.db_manager.set_run_status, self.event_id, 'rejected')
            print(f"Run {self.event_id} timed out and was rejected.")
            # self.stop() is called automatically

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensures only the original user can click the buttons."""
        
        # This is the correct check:
        # Is the person clicking the button the same person
        # we stored from the /submit command?
        if interaction.user.id != self.original_user_id:
            await interaction.response.send_message("You are not the author of this submission.", ephemeral=True)
            return False
        
        # Check if the view has already been actioned (Confirm/Cancel)
        if self.has_been_actioned and interaction.data.get('custom_id') != 'edit_run':
             await interaction.response.send_message("This submission has already been processed.", ephemeral=True)
             return False
             
        return True