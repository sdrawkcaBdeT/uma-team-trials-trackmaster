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
    
    # Create headers
    names = ["**Uma Name**"]
    epithets = ["**Epithet**"]
    teams = ["**Team**"]
    pts = ["**Score**"]
    
    # Add rows
    for uma in scores:
        names.append(uma.get('name', 'N/A'))
        epithets.append(uma.get('epithet', 'N/A')) # <-- ADDED
        teams.append(uma.get('team', 'N/A'))
        pts.append(f"{uma.get('score', 0):,}")

    # Find longest strings for padding
    max_name_len = max(len(n) for n in names)
    max_epithet_len = max(len(e) for e in epithets) # <-- ADDED
    max_team_len = max(len(t) for t in teams)
    
    # Build the table string
    table_string = ""
    for name, epithet, team, score in zip(names, epithets, teams, pts):
        # Pad strings to align columns
        table_string += f"{name.ljust(max_name_len)} | {epithet.ljust(max_epithet_len)} | {team.ljust(max_team_len)} | {score}\n" # <-- ADDED
        
    embed.add_field(
        name="Extracted Scores",
        value=f"```md\n{table_string}\n```", # "md" provides syntax highlighting
        inline=False
    )
    
    if warning:
        embed.add_field(
            name="⚠️ Warning", # Changed from "!!!"
            value=warning,
            inline=False
        )
        
    embed.set_footer(text="Click 'Confirm', 'Edit', or 'Cancel' below.")
    return embed