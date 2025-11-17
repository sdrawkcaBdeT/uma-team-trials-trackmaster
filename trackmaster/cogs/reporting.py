# trackmaster/cogs/reporting.py

import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
import pandas as pd
from typing import Optional
import os

from trackmaster.bot import TrackmasterBot
from trackmaster.ui.images import generate_leaderboard_image, generate_team_summary_image

logger = logging.getLogger(__name__)

class ReportingCog(commands.Cog):
    def __init__(self, bot: TrackmasterBot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Shows your personal Uma leaderboard.")
    @app_commands.describe(
        roster_id="Optional: Filter by a specific Roster ID.",
        week="Optional: Filter by a specific week (e.g., 2025-W46)."
    )
    async def personal_leaderboard(self, interaction: discord.Interaction, roster_id: Optional[int] = None, week: Optional[str] = None):
        await interaction.response.defer()
        
        # --- BUILD TITLE AND GET DATA ---
        title = f"{interaction.user.display_name}'s Personal Leaderboard"
        desc_parts = ["Showing your personal scores from all *approved* runs."]
        if roster_id:
            desc_parts.append(f"Filtered by Roster ID: **{roster_id}**")
            title += f" (Roster {roster_id})"
        if week:
            desc_parts.append(f"Filtered by Week: **{week}**")
            title += f" (Week {week})"

        leaderboard_df = await asyncio.to_thread(
            self.bot.db_manager.get_leaderboard_data,
            user_id=interaction.user.id,
            roster_id=roster_id,
            week=week
        )

        # --- SORT AS REQUESTED ---
        if leaderboard_df is not None and not leaderboard_df.empty:
            leaderboard_df = leaderboard_df.sort_values(by="avg_score", ascending=False)
        
        # --- GENERATE IMAGE ---
        image_path = await asyncio.to_thread(
            generate_leaderboard_image, leaderboard_df, title
        )

        # --- SEND IMAGE ---
        if image_path:
            await interaction.followup.send(file=discord.File(image_path))
            os.remove(image_path) # Clean up the temp file
        else:
            await interaction.followup.send("Sorry, I couldn't generate the leaderboard image.")

    @app_commands.command(name="leaderboard_global", description="Shows the server-wide (all users) Uma leaderboard.")
    @app_commands.describe(
        roster_id="Optional: Filter by a specific Roster ID.",
        week="Optional: Filter by a specific week (e.g., 2025-W46)."
    )
    async def global_leaderboard(self, interaction: discord.Interaction, roster_id: Optional[int] = None, week: Optional[str] = None):
        await interaction.response.defer()
        
        # --- BUILD TITLE AND GET DATA ---
        title = "Global Uma Leaderboard"
        desc_parts = ["Showing scores for *all users* from all *approved* runs."]
        if roster_id:
            desc_parts.append(f"Filtered by Roster ID: **{roster_id}**")
            title += f" (Roster {roster_id})"
        if week:
            desc_parts.append(f"Filtered by Week: **{week}**")
            title += f" (Week {week})"

        leaderboard_df = await asyncio.to_thread(
            self.bot.db_manager.get_leaderboard_data,
            user_id=None,
            roster_id=roster_id,
            week=week
        )

        # --- SORT AS REQUESTED ---
        if leaderboard_df is not None and not leaderboard_df.empty:
            leaderboard_df = leaderboard_df.sort_values(by="avg_score", ascending=False)
        
        # --- GENERATE IMAGE ---
        image_path = await asyncio.to_thread(
            generate_leaderboard_image, leaderboard_df, title
        )

        # --- SEND IMAGE ---
        if image_path:
            await interaction.followup.send(file=discord.File(image_path))
            os.remove(image_path)
        else:
            await interaction.followup.send("Sorry, I couldn't generate the leaderboard image.")

    @app_commands.command(name="team_summary", description="Shows your personal team performance summary.")
    @app_commands.describe(
        roster_id="Optional: Filter by a specific Roster ID.",
        week="Optional: Filter by a specific week (e.g., 2025-W46)."
    )
    async def personal_team_summary(self, interaction: discord.Interaction, roster_id: Optional[int] = None, week: Optional[str] = None):
        await interaction.response.defer()
        
        # --- BUILD TITLE AND GET DATA ---
        title = f"{interaction.user.display_name}'s Team Summary"
        desc_parts = ["Showing your personal team scores from all *approved* runs."]
        if roster_id:
            desc_parts.append(f"Filtered by Roster ID: **{roster_id}**")
            title += f" (Roster {roster_id})"
        if week:
            desc_parts.append(f"Filtered by Week: **{week}**")
            title += f" (Week {week})"

        team_summary_df = await asyncio.to_thread(
            self.bot.db_manager.get_team_summary_data,
            user_id=interaction.user.id,
            roster_id=roster_id,
            week=week
        )

        # --- SORT AS REQUESTED ---
        if team_summary_df is not None and not team_summary_df.empty:
            team_summary_df = team_summary_df.sort_values(by="AvgTeamBest", ascending=False)

        # --- GENERATE IMAGE ---
        image_path = await asyncio.to_thread(
            generate_team_summary_image, team_summary_df, title
        )
        
        # --- SEND IMAGE ---
        if image_path:
            await interaction.followup.send(file=discord.File(image_path))
            os.remove(image_path)
        else:
            await interaction.followup.send("Sorry, I couldn't generate the team summary image.")

    @app_commands.command(name="team_summary_global", description="Shows the server-wide team performance summary.")
    @app_commands.describe(
        roster_id="Optional: Filter by a specific Roster ID.",
        week="Optional: Filter by a specific week (e.g., 2025-W46)."
    )
    async def global_team_summary(self, interaction: discord.Interaction, roster_id: Optional[int] = None, week: Optional[str] = None):
        await interaction.response.defer()
        
        # --- BUILD TITLE AND GET DATA ---
        title = "Global Team Performance Summary"
        desc_parts = ["Showing team scores for *all users* from all *approved* runs."]
        if roster_id:
            desc_parts.append(f"Filtered by Roster ID: **{roster_id}**")
            title += f" (Roster {roster_id})"
        if week:
            desc_parts.append(f"Filtered by Week: **{week}**")
            title += f" (Week {week})"

        team_summary_df = await asyncio.to_thread(
            self.bot.db_manager.get_team_summary_data,
            user_id=None,
            roster_id=roster_id,
            week=week
        )

        # --- SORT AS REQUESTED ---
        if team_summary_df is not None and not team_summary_df.empty:
            team_summary_df = team_summary_df.sort_values(by="AvgTeamBest", ascending=False)
            
        # --- GENERATE IMAGE ---
        image_path = await asyncio.to_thread(
            generate_team_summary_image, team_summary_df, title
        )
        
        # --- SEND IMAGE ---
        if image_path:
            await interaction.followup.send(file=discord.File(image_path))
            os.remove(image_path)
        else:
            await interaction.followup.send("Sorry, I couldn't generate the team summary image.")

async def setup(bot: TrackmasterBot):
    await bot.add_cog(ReportingCog(bot))