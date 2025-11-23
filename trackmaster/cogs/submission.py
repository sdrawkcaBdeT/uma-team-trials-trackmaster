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
    
        await interaction.response.defer(ephemeral=True) 

        attachments = [img for img in [image1, image2, image3, image4] if img is not None]
        temp_image_paths = []
        all_uma_scores = []
        image_warnings = []

        try:
            # Process images SEQUENTIALLY to save GPU VRAM
            for i, attachment in enumerate(attachments):
                if not attachment.content_type.startswith("image/"):
                    image_warnings.append(f"⚠️ `{attachment.filename}` is not an image.")
                    continue
                
                # 1. Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix=attachment.filename) as tmp:
                    await attachment.save(tmp.name)
                    temp_image_paths.append(tmp.name)

                    # 2. Run OCR (Blocking, one at a time)
                    # We use to_thread to keep the Discord bot responsive, 
                    # but we await it immediately so we don't overload the GPU.
                    result_text = await asyncio.to_thread(
                        run_ocr_sync, self.bot.extractor, tmp.name
                    )
                    
                    # 3. Parse and Verify
                    try:
                        if not result_text:
                            image_warnings.append(f"❌ `{attachment.filename}`: No text found.")
                            continue

                        ocr_data = json.loads(result_text)
                        scores = ocr_data.get("uma_scores", [])
                        
                        # --- THE CRITICAL FIX ---
                        # Check if we found fewer than 5 racers in this specific image
                        if len(scores) < 5:
                            image_warnings.append(f"⚠️ `{attachment.filename}`: Only found **{len(scores)}/5** racers. Check this carefully!")
                        
                        all_uma_scores.extend(scores)
                        
                    except (json.JSONDecodeError, ValueError):
                        image_warnings.append(f"❌ `{attachment.filename}`: Failed to read data.")

            if not all_uma_scores:
                await interaction.followup.send("I couldn't extract any data. Please try again with clearer screenshots.", ephemeral=True)
                return
            
            # 4. Validate (using the improved validation logic from Fix 1)
            validator = ValidationService(self.bot.db_manager)
            validation_result = await validator.validate_and_correct(all_uma_scores)
            
            final_roster_id = roster_id
            if final_roster_id is None:
                final_roster_id = await asyncio.to_thread(
                    self.bot.db_manager.get_user_active_roster,
                    interaction.user.id
                )
            
            # 5. Save to DB
            event_id = await asyncio.to_thread(
                self.bot.db_manager.create_pending_run,
                interaction.user.id,
                str(interaction.user),
                final_roster_id, 
                validation_result.corrected_scores
            )

            # 6. Compile Warnings
            final_warnings = []
            final_warnings.extend(image_warnings) # Add our specific image warnings
            
            if len(all_uma_scores) != 15:
                final_warnings.append(f"**Total Count Alert:** Found {len(all_uma_scores)} Umas (Expected 15).")
            
            if validation_result.low_confidence_count > 0:
                final_warnings.append(f"**Low Confidence:** Unsure about {validation_result.low_confidence_count} name(s).")

            warning_message = ""
            if final_warnings:
                warning_message = "\n".join(final_warnings)

            embed = create_score_embed(validation_result.corrected_scores, event_id, warning_message)
            
            view = ValidationView(
                bot=self.bot, 
                event_id=event_id, 
                corrected_data=validation_result.corrected_scores,
                original_user_id=interaction.user.id
            )
            
            await interaction.followup.send(
                f"Run **{event_id}** (Roster {final_roster_id}) processed.", 
                embed=embed,
                view=view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in /submit command", exc_info=e)
            await interaction.followup.send("An unexpected error occurred.", ephemeral=True)
        
        finally:
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