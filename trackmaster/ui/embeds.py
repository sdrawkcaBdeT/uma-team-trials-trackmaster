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
    epithets = ["**Epithet**"]
    teams = ["**Team**"]
    pts = ["**Score**"]
    
    # Add rows
    for uma in scores:
        names.append(uma.get('name', 'N/A'))
        epithets.append(uma.get('epithet', 'N/A'))
        teams.append(uma.get('team', 'N/A'))
        pts.append(f"{uma.get('score', 0):,}") # Add commas to score

    # Find the longest name for padding
    max_name_len = max(len(n) for n in names)
    max_epithet_len = max(len(e) for e in epithets)
    max_team_len = max(len(t) for t in teams)
    
    # Build the table string
    table_string = ""
    for name, epithet, team, score in zip(names, epithets, teams, pts):
        # Pad strings to align columns
        table_string += f"{name.ljust(max_name_len)} | {epithet.ljust(max_epithet_len)} | {team.ljust(max_team_len)} | {score}\n"
        
    embed.add_field(
        name="Extracted Scores",
        value=f"```md\n{table_string}\n```", # "md" provides syntax highlighting
        inline=False
    )
    
    if warning:
        embed.add_field(
            name="⚠️ Warning",
            value=warning,
            inline=False
        )
        
    embed.set_footer(text="Click 'Confirm', 'Edit', or 'Cancel' below.")
    return embed

# --- NEW FUNCTION ---
def create_confirmation_embed(event_id: str, scores: List[Dict[str, Any]]) -> discord.Embed:
    """
    Creates a green "Confirmed" embed after a run is saved.
    """
    embed = discord.Embed(
        title=f"✅ Run Confirmed: {event_id}",
        description=f"This run with {len(scores)} Umas has been successfully saved to the leaderboard.",
        color=discord.Color.green()
    )

    # Re-create the table string, just like in create_score_embed
    names = ["**Uma Name**"]
    epithets = ["**Epithet**"]
    teams = ["**Team**"]
    pts = ["**Score**"]
    
    for uma in scores:
        names.append(uma.get('name', 'N/A'))
        epithets.append(uma.get('epithet', 'N/A'))
        teams.append(uma.get('team', 'N/A'))
        pts.append(f"{uma.get('score', 0):,}")

    max_name_len = max(len(n) for n in names)
    max_epithet_len = max(len(e) for e in epithets)
    max_team_len = max(len(t) for t in teams)
    
    table_string = ""
    for name, epithet, team, score in zip(names, epithets, teams, pts):
        table_string += f"{name.ljust(max_name_len)} | {epithet.ljust(max_epithet_len)} | {team.ljust(max_team_len)} | {score}\n"
        
    embed.add_field(
        name="Final Confirmed Data",
        value=f"```md\n{table_string}\n```",
        inline=False
    )
    
    embed.set_footer(text="You can now run /leaderboard or /team_summary to see the new stats.")
    return embed