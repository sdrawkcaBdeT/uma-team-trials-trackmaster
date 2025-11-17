# trackmaster/cogs/submission.py

import discord
from discord import app_commands
from discord.ext import commands
import tempfile
import os
import json
import logging
import asyncio

from trackmaster.bot import TrackmasterBot
from trackmaster.core.validation import ValidationService
from trackmaster.ui.views import ValidationView
from trackmaster.ui.embeds import create_score_embed

logger = logging.getLogger(__name__)

# --- NEW HELPER FUNCTION ---
def run_ocr_sync(extractor, image_path: str) -> str:
    """
    This is the synchronous, blocking function that will be run in a thread.
    """
    try:
        return extractor.extract(image_path).extract_text().strip()
    except Exception as e:
        logger.error(f"OCR process failed for {image_path}: {e}")
        return "" # Return empty string on failure
# --- END HELPER FUNCTION ---


class SubmissionCog(commands.Cog):
    def __init__(self, bot: TrackmasterBot):
        self.bot = bot

    @app_commands.command(name="submit", description="Submits a new team trial run.")
    @app_commands.describe(
        image1="The first screenshot (e.g., racers 1-5).",
        image2="The second screenshot (e.g., racers 6-10).",
        image3="The third screenshot (e.g., racers 11-15).",
        roster_id="Optional: Specify a roster ID. If blank, uses your active roster.",
        image4="Optional: A fourth screenshot if your run has more than 15 racers."
    )
    async def submit_trial(
        self,
        interaction: discord.Interaction,
        image1: discord.Attachment,
        image2: discord.Attachment,
        image3: discord.Attachment,
        roster_id: int = None,
        image4: discord.Attachment = None
    ):
    
        # 1. Defer response immediately
        await interaction.response.defer(ephemeral=True) 

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

                    # 3. Run OCR in a separate thread
                    #    --- THIS IS THE FIRST FIX ---
                    result_text = await asyncio.to_thread(
                        run_ocr_sync, self.bot.extractor, tmp.name
                    )
                    
                    raw_ocr_outputs.append(result_text)

                    # 4. Basic JSON check
                    try:
                        if not result_text:
                            raise ValueError("OCR returned no text.")
                            
                        ocr_data = json.loads(result_text)
                        if "uma_scores" not in ocr_data or not ocr_data["uma_scores"]:
                            raise ValueError("JSON missing 'uma_scores' or list is empty.")
                        
                        all_uma_scores.extend(ocr_data["uma_scores"])
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Failed to parse OCR for {attachment.filename}: {e}\nRaw: {result_text}")
                        await interaction.followup.send(
                            f"Sorry, I couldn't read the data from `{attachment.filename}`. "
                            f"It might be a cat photo or a bad screenshot. Please try again.\n\n"
                            f"```\n{result_text}\n```", 
                            ephemeral=True
                        )
                        return # Hard fail on bad parse

            if not all_uma_scores:
                await interaction.followup.send("I couldn't find any score data in those images.", ephemeral=True)
                return
            
            # 5. Validate and Correct Data
            validator = ValidationService(self.bot.db_manager)
            #    --- THIS IS THE SECOND FIX (see validation.py) ---
            validation_result = await validator.validate_and_correct(all_uma_scores)
            
            final_roster_id = roster_id
            if final_roster_id is None:
                # Roster not provided, get their active one
                final_roster_id = await asyncio.to_thread(
                    self.bot.db_manager.get_user_active_roster,
                    interaction.user.id
                )
            
            # 6. Save to DB with 'pending_validation' status
            event_id = await asyncio.to_thread(
                self.bot.db_manager.create_pending_run,
                interaction.user.id,
                str(interaction.user),
                final_roster_id, 
                validation_result.corrected_scores
            )

            # 7. Send to User for Validation
            warnings = []
            if len(all_uma_scores) != 15:
                warnings.append(f"I found {len(all_uma_scores)} Umas (expected 15).")
            if validation_result.low_confidence_count > 0:
                warnings.append(f"I had trouble reading {validation_result.low_confidence_count} name(s).")

            warning_message = ""
            if warnings:
                warning_message = "Warning: " + " ".join(warnings) + " Please check carefully."


            # Create the embed
            embed = create_score_embed(validation_result.corrected_scores, event_id, warning_message)
            
            # Send the confirmation buttons
            view = ValidationView(
                bot=self.bot, 
                event_id=event_id, 
                corrected_data=validation_result.corrected_scores,
                original_user_id=interaction.user.id
            )
            
            await interaction.followup.send(
                f"Here's what I extracted for run **{event_id}** (Roster ID: {final_roster_id}). Does this look correct?\n\n{warning_message}", 
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