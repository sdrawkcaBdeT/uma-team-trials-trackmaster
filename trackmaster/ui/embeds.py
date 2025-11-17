# trackmaster/ui/embeds.py

import discord
from typing import List, Dict, Any

def create_score_embed(scores: List[Dict[str, Any]], event_id: str, warning: str = None) -> discord.Embed:
    """
    Creates a Discord Embed to display the extracted scores for validation.
    """
    
    embed = discord.Embed(
        title=f"Pending Run: {event_id}",
        description="Please review the extracted data below.",
        color=discord.Color.orange() # Orange for "pending"
    )

    # We have to build the table in-place. Discord embeds don't have tables,
    # so we use code blocks for perfect alignment.
    
    # Create headers
    names = ["**Uma Name**"]
    teams = ["**Team**"]
    pts = ["**Score**"]
    
    # Add rows
    for uma in scores:
        names.append(uma.get('name', 'N/A'))
        teams.append(uma.get('team', 'N/A'))
        pts.append(f"{uma.get('score', 0):,}") # Add commas to score

    # Find the longest name for padding
    max_name_len = max(len(n) for n in names)
    max_team_len = max(len(t) for t in teams)
    
    # Build the table string
    table_string = ""
    for name, team, score in zip(names, teams, pts):
        # Pad strings to align columns
        table_string += f"{name.ljust(max_name_len)} | {team.ljust(max_team_len)} | {score}\n"
        
    embed.add_field(
        name="Extracted Scores",
        value=f"```md\n{table_string}\n```", # "md" provides syntax highlighting
        inline=False
    )
    
    if warning:
        embed.add_field(
            name="!!! Warning",
            value=warning,
            inline=False
        )
        
    embed.set_footer(text="Click 'Confirm', 'Edit', or 'Cancel' below.")
    return embed