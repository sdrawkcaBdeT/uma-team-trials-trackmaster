# trackmaster/cogs/help.py
import discord
from discord import app_commands
from discord.ext import commands
from trackmaster.bot import TrackmasterBot

class HelpCog(commands.Cog):
    def __init__(self, bot: TrackmasterBot):
        self.bot = bot

    @app_commands.command(name="help", description="Shows the user guide for the Trackmaster bot.")
    async def help_command(self, interaction: discord.Interaction):
        
        embed = discord.Embed(
            title="Uma-Team-Trials Trackmaster Guide",
            description="Welcome! I record and report your Team Trial scores.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="1. How to Submit a Run",
            value=(
                "1. Use the `/submit` command.\n"
                "2. Attach your two (or more) screenshots of the 'Score Info' page to the `image1` and `image2` options.\n"
                "3. (Optional) Add a `roster_id` if you want to track this run on a specific roster (e.g., `1`, `2`).\n"
                "4. I will scan the images and show you what I found."
            ),
            inline=False
        )
        
        embed.add_field(
            name="2. The Validation Step",
            value=(
                "After you submit, I will ask you to confirm the data.\n"
                "• **[Confirm]**: Saves the run to the leaderboard.\n"
                "• **[Edit]**: Pops up a form to fix any typos in a name, team, or score.\n"
                "• **[Cancel]**: Deletes the submission."
            ),
            inline=False
        )

        embed.add_field(
            name="3. Roster Management (Your Teams)",
            value=(
                "You can track different rosters over time.\n"
                "• `/set_roster <id>`: Sets your 'active' roster. Any `/submit` run *without* a `roster_id` will be assigned to this one. (Default is `1`).\n"
                "• `/submit roster_id:2`: Submits a run specifically to Roster 2, without changing your active roster."
            ),
            inline=False
        )
        
        embed.add_field(
            name="4. Reporting Commands",
            value=(
                "• `/leaderboard [roster_id] [week]`: Shows the all-time best scores for each Uma. You can optionally filter by roster or week (e.g., `week:2025-W46`).\n"
                "• `/team_summary [roster_id] [week]`: Shows the performance summary for each team (Sprint, Mile, etc.). Can also be filtered by roster or week."
            ),
            inline=False
        )
        
        embed.set_footer(text="Good luck in your trials!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: TrackmasterBot):
    await bot.add_cog(HelpCog(bot))