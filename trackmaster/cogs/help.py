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
                "2. **Recommended:** Attach 3 screenshots, each showing 5 racers (for a total of 15).\n"
                "3. You must attach at least `image1`, `image2`, and `image3`.\n"
                "4. (Optional) Add a `roster_id` if you want to track this run on a specific roster (e.g., `1`, `2`).\n"
                "5. I will scan the images and show you what I found."
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
        
        # --- THIS SECTION IS UPDATED ---
        embed.add_field(
            name="4. Reporting Commands",
            value=(
                "**Personal Reports (Just for you):**\n"
                "• `/leaderboard [roster_id] [week]`: Shows *your* personal Uma leaderboard.\n"
                "• `/team_summary [roster_id] [week]`: Shows *your* personal team performance.\n\n"
                "**Global Reports (All users):**\n"
                "• `/leaderboard_global [roster_id] [week]`: Shows the server-wide Uma leaderboard.\n"
                "• `/team_summary_global [roster_id] [week]`: Shows the server-wide team performance."
            ),
            inline=False
        )
        # --- END OF UPDATES ---
        
        embed.set_footer(text="Good luck in your trials!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: TrackmasterBot):
    await bot.add_cog(HelpCog(bot))