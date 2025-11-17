# trackmaster/ui/modals.py
import discord
import asyncio
from trackmaster.bot import TrackmasterBot

class ScoreEditModal(discord.ui.Modal, title="Edit Score"):
    """
    A modal to edit a single Uma's score.
    """
    # This modal is designed to be simple. It does not pre-fill data.
    # It asks the user to identify the one they want to fix.
    
    name_to_correct = discord.ui.TextInput(
        label="Uma Name to Correct",
        placeholder="Type the name exactly as the bot found it (e.g., 'Maruzcnsky')",
        style=discord.TextStyle.short,
        required=True
    )
    
    corrected_name = discord.ui.TextInput(
        label="Corrected Name",
        placeholder="The correct character name (e.g., 'Maruzensky')",
        style=discord.TextStyle.short,
        required=True
    )

    corrected_team = discord.ui.TextInput(
        label="Corrected Team",
        placeholder="The correct team (e.g., 'Mile', 'Sprint', etc.)",
        style=discord.TextStyle.short,
        required=True
    )
    
    corrected_score = discord.ui.TextInput(
        label="Corrected Score",
        placeholder="The correct score (e.g., '46730')",
        style=discord.TextStyle.short,
        required=True
    )

    def __init__(self, bot: TrackmasterBot, event_id: str):
        super().__init__()
        self.bot = bot
        self.event_id = event_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        # 1. Parse the score
        try:
            score_num = int(self.corrected_score.value.replace(",", ""))
        except ValueError:
            await interaction.followup.send("Error: The score must be a number (e.g., '46730').", ephemeral=True)
            return

        # 2. Call the DB function in a thread
        success = await asyncio.to_thread(
            self.bot.db_manager.update_single_score,
            event_id=self.event_id,
            original_name=self.name_to_correct.value,
            new_name=self.corrected_name.value,
            new_team=self.corrected_team.value,
            new_score=score_num
        )

        if success:
            await interaction.followup.send(
                f"✅ **Edit Applied!**\n"
                f"`{self.name_to_correct.value}` -> `{self.corrected_name.value}` with score `{score_num}`.\n\n"
                f"**Note:** The embed won't update automatically. Click 'Confirm' when you're done with all edits.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"❌ **Edit Failed!**\n"
                f"I couldn't find an entry named `{self.name_to_correct.value}` in this run. "
                f"Please copy the name *exactly* as it appears in the table.",
                ephemeral=True
            )