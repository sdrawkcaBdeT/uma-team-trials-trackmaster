# trackmaster/cogs/reporting.py

import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
import pandas as pd
from typing import Optional

from trackmaster.bot import TrackmasterBot

logger = logging.getLogger(__name__)

def format_df_for_discord(df: pd.DataFrame) -> str:
    """Converts a DataFrame to a Discord-friendly markdown code block."""
    if df is None or df.empty:
        return "No data found."
    
    # Convert to string and add to code block
    output = f"```md\n{df.to_string(index=False)}\n```"
    
    # Discord's message limit is 2000 chars.
    if len(output) > 1990:
        output = f"```md\n{df.to_string(index=False, max_rows=15)}\n```\n...and more (too large to display)."
    return output

class ReportingCog(commands.Cog):
    def __init__(self, bot: TrackmasterBot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Shows the all-time leaderboard for Umas.")
    @app_commands.describe(
        roster_id="Optional: Filter by a specific Roster ID.",
        week="Optional: Filter by a specific week (e.g., 2025-W46)."
    )
    async def leaderboard(self, interaction: discord.Interaction, roster_id: Optional[int] = None, week: Optional[str] = None):
        await interaction.response.defer()
        
        # Run the synchronous DB query in a thread
        leaderboard_df = await asyncio.to_thread(
            self.bot.db_manager.get_leaderboard_data,
            roster_id=roster_id,
            week=week
        )
        
        # Build description
        desc_parts = ["Showing scores for all *approved* runs."]
        if roster_id:
            desc_parts.append(f"Filtered by Roster ID: **{roster_id}**")
        if week:
            desc_parts.append(f"Filtered by Week: **{week}**")
        
        embed = discord.Embed(
            title="All-Time Uma Leaderboard",
            description="\n".join(desc_parts),
            color=discord.Color.blue()
        )
        embed.add_field(name="Leaderboard", value=format_df_for_discord(leaderboard_df), inline=False)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="team_summary", description="Shows the leaderboard by team (Sprint, Mile, etc.).")
    @app_commands.describe(
        roster_id="Optional: Filter by a specific Roster ID.",
        week="Optional: Filter by a specific week (e.g., 2025-W46)."
    )
    async def team_summary(self, interaction: discord.Interaction, roster_id: Optional[int] = None, week: Optional[str] = None):
        await interaction.response.defer()
        
        # Run the synchronous DB query in a thread
        team_summary_df = await asyncio.to_thread(
            self.bot.db_manager.get_team_summary_data,
            roster_id=roster_id,
            week=week
        )
        
        # Build description
        desc_parts = ["Showing team scores for all *approved* runs."]
        if roster_id:
            desc_parts.append(f"Filtered by Roster ID: **{roster_id}**")
        if week:
            desc_parts.append(f"Filtered by Week: **{week}**")
        
        embed = discord.Embed(
            title="Team Performance Summary",
            description="\n".join(desc_parts),
            color=discord.Color.blue()
        )
        embed.add_field(name="Team Summary", value=format_df_for_discord(team_summary_df), inline=False)
        
        await interaction.followup.send(embed=embed)

async def setup(bot: TrackmasterBot):
    await bot.add_cog(ReportingCog(bot))