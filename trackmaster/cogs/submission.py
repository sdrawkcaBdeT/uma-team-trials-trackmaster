# trackmaster/cogs/submission.py

import discord
from discord import app_commands
from discord.ext import commands
import tempfile
import os
import json
import logging
import asyncio

from trackmaster.bot import TrackmasterBot # Used for type hinting
from trackmaster.core.validation import ValidationService
from trackmaster.ui.views import ValidationView # We will create this
from trackmaster.ui.embeds import create_score_embed

logger = logging.getLogger(__name__)

class SubmissionCog(commands.Cog):
    def __init__(self, bot: TrackmasterBot):
        self.bot = bot

    @app_commands.command(name="submit", description="Submits a new team trial run.")
    @app_commands.describe(
        image1="The first screenshot of your scores (Top 8).",
        image2="The second screenshot of your scores (Bottom 7).",
        roster_id="Optional: Specify a roster ID. If blank, uses your active roster.",
        image3="Optional: A third screenshot.",
        image4="Optional: A fourth screenshot."
    )
    async def submit_trial(
        self,
        interaction: discord.Interaction,
        image1: discord.Attachment,
        image2: discord.Attachment,
        roster_id: int = None,
        image3: discord.Attachment = None,
        image4: discord.Attachment = None
    ):
        # 1. Defer response immediately
        await interaction.response.defer(ephemeral=True) # ephemeral=True keeps it private

        attachments = [img for img in [image1, image2, image3, image4] if img is not None]
        temp_image_paths = []
        all_uma_scores = []
        raw_ocr_outputs = []

        try:
            # 2. Process all images
            for attachment in attachments:
                if not attachment.content_type.startswith("image/"):
                    await interaction.followup.send(f"Error: {attachment.filename} is not an image.", ephemeral=True)
                    return
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=attachment.filename) as tmp:
                    await attachment.save(tmp.name)
                    temp_image_paths.append(tmp.name)

                    # 3. Run OCR
                    # This now uses our patched extractor with the custom prompt
                    result_text = self.bot.extractor.extract(tmp.name).extract_text().strip()
                    raw_ocr_outputs.append(result_text)

                    # 4. Basic JSON check
                    try:
                        ocr_data = json.loads(result_text)
                        if "uma_scores" not in ocr_data or not ocr_data["uma_scores"]:
                            raise ValueError("JSON missing 'uma_scores' or list is empty.")
                        
                        all_uma_scores.extend(ocr_data["uma_scores"])
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Failed to parse OCR for {attachment.filename}: {e}\nRaw: {result_text}")
                        await interaction.followup.send(
                            f"Sorry, I couldn't read the data from `{attachment.filename}`. "
                            "It might be a cat photo or a bad screenshot. Please try again.", 
                            ephemeral=True
                        )
                        return # Hard fail on bad parse

            if not all_uma_scores:
                await interaction.followup.send("I couldn't find any score data in those images.", ephemeral=True)
                return
            
            # 5. Validate and Correct Data
            validator = ValidationService(self.bot.db_manager) # Pass the DB manager
            validation_result = await validator.validate_and_correct(all_uma_scores)
            
            final_roster_id = roster_id
            if final_roster_id is None:
                # Roster not provided, get their active one
                final_roster_id = await asyncio.to_thread(
                    self.bot.db_manager.get_user_active_roster,
                    interaction.user.id
                )
            
            # 6. Save to DB with 'pending_validation' status
            # We call the SYNCHRONOUS DB function in a separate thread
            event_id = await asyncio.to_thread(
                self.bot.db_manager.create_pending_run,
                interaction.user.id,
                str(interaction.user),
                final_roster_id, 
                validation_result.corrected_scores
            )

            # 7. Send to User for Validation

            warnings = []

            # FIX 1: This is now a proper f-string
            if len(all_uma_scores) != 15:
                warnings.append(f"I found {len(all_uma_scores)} Umas (expected 15).")

            if validation_result.low_confidence_count > 0:
                warnings.append(f"I had trouble reading {validation_result.low_confidence_count} name(s).")

            # Combine warnings into one message
            warning_message = ""
            if warnings:
                # This joins them, e.g., "Warning: I found 14 Umas... I had trouble reading 1 name(s)..."
                warning_message = "Warning: " + " ".join(warnings) + " Please check carefully."


            # Create the embed
            embed = create_score_embed(validation_result.corrected_scores, event_id, warning_message)
            
            # Send the confirmation buttons
            view = ValidationView(
                bot=self.bot, 
                event_id=event_id, 
                corrected_data=validation_result.corrected_scores
            )
            
            await interaction.followup.send(
                f"Here's what I extracted for run **{event_id}**. Does this look correct?\n\n{warning_message}", 
                embed=embed,
                view=view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in /submit command", exc_info=e)
            await interaction.followup.send("An unexpected error occurred. The developers have been notified.", ephemeral=True)
        
        finally:
            # 8. Clean up temp files
            for path in temp_image_paths:
                if os.path.exists(path):
                    os.remove(path)
                    
    @app_commands.command(name="set_roster", description="Sets your active roster ID (e.g., 1, 2, 3) for future runs.")
    @app_commands.describe(roster_id="The ID you want to set as active (e.g., 1).")
    async def set_active_roster(self, interaction: discord.Interaction, roster_id: int):
        await interaction.response.defer(ephemeral=True)
        
        if roster_id <= 0:
            await interaction.followup.send("Roster ID must be a positive number.", ephemeral=True)
            return

        success = await asyncio.to_thread(
            self.bot.db_manager.set_user_active_roster,
            interaction.user.id,
            roster_id
        )
        if success:
            await interaction.followup.send(f"Your active roster ID is now set to **{roster_id}**.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred while setting your roster.", ephemeral=True)


async def setup(bot: TrackmasterBot):
    await bot.add_cog(SubmissionCog(bot))