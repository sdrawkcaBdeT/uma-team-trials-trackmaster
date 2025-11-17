# trackmaster/ui/images.py

import matplotlib.pyplot as plt
import pandas as pd
import os
import tempfile
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# --- Matplotlib Configuration (from your styling code) ---
# This defines the consistent dark theme
plt.rcParams['figure.facecolor'] = '#2E2E2E'
plt.rcParams['text.color'] = '#E0E0E0'
plt.rcParams['axes.labelcolor'] = '#A0A0A0'
plt.rcParams['xtick.color'] = '#A0A0A0'
plt.rcParams['ytick.color'] = '#A0A0A0'
plt.rcParams['axes.edgecolor'] = '#414868'
plt.rcParams['axes.facecolor'] = '#2E2E2E'
plt.rcParams['grid.color'] = '#414868'
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['figure.dpi'] = 150 # You can adjust this for file size vs quality
plt.style.use('seaborn-v0_8-whitegrid')
# --- End Styling ---

def _add_timestamps_to_fig(fig, generated_str):
    """Helper to add timestamps to the bottom of the image."""
    now_utc = datetime.utcnow()
    ct_time = now_utc.strftime('%m/%d/%Y %I:%M:%S %p CT')
    
    fig.text(0.01, 0.01, f"Generated: {ct_time}", color='#A0A0A0', fontsize=9, ha='left')
    fig.text(0.99, 0.01, f"{generated_str}", color='#A0A0A0', fontsize=9, ha='right')

def generate_leaderboard_image(df: pd.DataFrame, title: str) -> str:
    """
    Generates and saves a CML-style image for the Leaderboard.
    Returns the file path to the generated image.
    """
    logger.info(f"Generating leaderboard image for: {title}")
    if df.empty:
        logger.warning("Leaderboard DataFrame is empty. Skipping image generation.")
        # We should still generate a "No Data" image
        df = pd.DataFrame(columns=['uma_name', 'epithet', 'team', 'max_score', 'avg_score', 'p95_score'])

    limit = 30 # Max rows to show
    
    # --- Setup Figure ---
    # Adjust height based on number of rows
    row_height = 1 / (limit + 5)
    fig_height = (len(df.head(limit)) + 4) * row_height * 10
    fig_height = max(5, min(15, fig_height)) # Clamp height
    
    fig, ax = plt.subplots(figsize=(16, fig_height))
    fig.patch.set_facecolor('#2E2E2E')
    ax.set_facecolor('#2E2E2E')
    ax.set_title(title, color='white', loc='left', pad=20, fontsize=16, weight='bold')

    # --- Headers ---
    headers = ['Uma Name', 'Epithet', 'Team', 'Max Score', 'Avg Score', 'P95 Score']
    # Tuned positions for 6 columns
    header_positions = [0.01, 0.25, 0.40, 0.55, 0.70, 0.85]
    
    for i, header in enumerate(headers):
        ax.text(header_positions[i], 0.935, header, color='#A0A0A0', fontsize=10, weight='bold', transform=ax.transAxes, va='top', ha='left')

    # --- Data Rows ---
    y_pos = 0.91
    for _, row in df.head(limit).iterrows():
        # Prepare strings
        name_str = str(row['uma_name'])
        epithet_str = str(row['epithet']) if pd.notna(row['epithet']) else '-'
        team_str = str(row['team'])
        max_str = f"{int(row['max_score']):,}"
        avg_str = f"{int(row['avg_score']):,}"
        p95_str = f"{int(row['p95_score']):,}"

        # Draw text
        ax.text(header_positions[0], y_pos, name_str, color='#E0E0E0', fontsize=12, transform=ax.transAxes, va='top', ha='left')
        ax.text(header_positions[1], y_pos, epithet_str, color='#BDBDBD', fontsize=11, transform=ax.transAxes, va='top', ha='left')
        ax.text(header_positions[2], y_pos, team_str, color='#E0E0E0', fontsize=12, transform=ax.transAxes, va='top', ha='left')
        ax.text(header_positions[3], y_pos, max_str, color='#FFD700', fontsize=12, weight='bold', transform=ax.transAxes, va='top', ha='left')
        ax.text(header_positions[4], y_pos, avg_str, color='#E0E0E0', fontsize=12, transform=ax.transAxes, va='top', ha='left')
        ax.text(header_positions[5], y_pos, p95_str, color='#64B5F6', fontsize=12, transform=ax.transAxes, va='top', ha='left')

        y_pos -= (1 / (limit + 5)) # Increment y-position

    # --- Final Touches ---
    _add_timestamps_to_fig(fig, f"{len(df)} Total Umas")
    ax.axis('off')

    # Save to a temporary file
    try:
        # Create a temp file and get its path
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            filepath = tmp_file.name
        
        plt.savefig(filepath, bbox_inches='tight', pad_inches=0.3, facecolor=fig.get_facecolor())
        plt.close(fig)
        logger.info(f"Successfully saved image to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to save image: {e}")
        plt.close(fig)
        return None

def generate_team_summary_image(df: pd.DataFrame, title: str) -> str:
    """
    Generates and saves a CML-style image for the Team Summary.
    Returns the file path to the generated image.
    """
    logger.info(f"Generating team summary image for: {title}")
    if df.empty:
        logger.warning("Team summary DataFrame is empty. Skipping image generation.")
        df = pd.DataFrame(columns=['team', 'AvgTeamBest', 'MedianTeamBest', 'P95TeamBest'])
        
    limit = 10 # Only 5 teams, so 10 is plenty
    
    # --- Setup Figure ---
    row_height = 1 / (limit + 5)
    fig_height = (len(df.head(limit)) + 4) * row_height * 10
    fig_height = max(5, min(10, fig_height))
    
    fig, ax = plt.subplots(figsize=(12, fig_height)) # Narrower figure
    fig.patch.set_facecolor('#2E2E2E')
    ax.set_facecolor('#2E2E2E')
    ax.set_title(title, color='white', loc='left', pad=20, fontsize=16, weight='bold')

    # --- Headers ---
    headers = ['Team', 'Avg Team Best', 'Median Team Best', 'P95 Team Best']
    header_positions = [0.01, 0.30, 0.55, 0.80] # 4 columns
    
    for i, header in enumerate(headers):
        ax.text(header_positions[i], 0.935, header, color='#A0A0A0', fontsize=10, weight='bold', transform=ax.transAxes, va='top', ha='left')

    # --- Data Rows ---
    y_pos = 0.91
    for _, row in df.head(limit).iterrows():
        # Prepare strings
        team_str = str(row['team'])
        avg_str = f"{int(row['AvgTeamBest']):,}"
        median_str = f"{int(row['MedianTeamBest']):,}"
        p95_str = f"{int(row['P95TeamBest']):,}"

        # Draw text
        ax.text(header_positions[0], y_pos, team_str, color='#E0E0E0', fontsize=12, transform=ax.transAxes, va='top', ha='left')
        ax.text(header_positions[1], y_pos, avg_str, color='#FFD700', fontsize=12, weight='bold', transform=ax.transAxes, va='top', ha='left')
        ax.text(header_positions[2], y_pos, median_str, color='#E0E0E0', fontsize=12, transform=ax.transAxes, va='top', ha='left')
        ax.text(header_positions[3], y_pos, p95_str, color='#64B5F6', fontsize=12, transform=ax.transAxes, va='top', ha='left')

        y_pos -= (1 / (limit + 5))

    # --- Final Touches ---
    _add_timestamps_to_fig(fig, f"{len(df)} Total Teams")
    ax.axis('off')

    # Save to a temporary file
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            filepath = tmp_file.name
        
        plt.savefig(filepath, bbox_inches='tight', pad_inches=0.3, facecolor=fig.get_facecolor())
        plt.close(fig)
        logger.info(f"Successfully saved image to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to save image: {e}")
        plt.close(fig)
        return None