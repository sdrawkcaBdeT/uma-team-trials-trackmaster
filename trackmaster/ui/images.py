# trackmaster/ui/images.py

import matplotlib
# Force non-interactive backend (Prevents GUI crashes on servers)
matplotlib.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.figure import Figure 
from matplotlib.backends.backend_agg import FigureCanvasAgg 
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
    logger.info(f"Generating leaderboard image for: {title}")
    if df.empty:
        df = pd.DataFrame(columns=['uma_name', 'epithet', 'team', 'max_score', 'avg_score', 'p95_score'])

    limit = 30 
    
    # --- SPACING FIX: Increase height multiplier per row ---
    # Previously: (len + 4) * row_height * 10. 
    # New: Simple linear calculation: Base of 2 inches + 0.4 inches per row.
    fig_height = 2 + (len(df.head(limit)) * 0.4)
    fig_height = max(5, min(20, fig_height)) # Cap at 20 inches
    
    fig = Figure(figsize=(16, fig_height))
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    
    fig.patch.set_facecolor('#2E2E2E')
    ax.set_facecolor('#2E2E2E')
    ax.set_title(title, color='white', loc='left', pad=20, fontsize=16, weight='bold')

    # --- Column Setup ---
    # Check if we have the 'trainer_name' column (Global Leaderboard)
    show_trainer = 'trainer_name' in df.columns
    
    if show_trainer:
        headers = ['Trainer', 'Uma Name', 'Epithet', 'Team', 'Max', 'Avg', 'P95']
        # Adjusted positions to fit Trainer at the front
        header_positions = [0.01, 0.15, 0.35, 0.50, 0.62, 0.75, 0.88]
    else:
        headers = ['Uma Name', 'Epithet', 'Team', 'Max Score', 'Avg Score', 'P95 Score']
        header_positions = [0.01, 0.25, 0.40, 0.55, 0.70, 0.85]

    # Draw Headers
    for i, header in enumerate(headers):
        ax.text(header_positions[i], 0.95, header, color='#A0A0A0', fontsize=11, weight='bold', transform=ax.transAxes, va='top', ha='left')

    # --- Data Rows ---
    # Start y_pos slightly lower to account for spacing
    y_start = 0.92
    # Calculate step size based on actual number of items to fill the space evenly-ish
    # or just use a fixed step size if we trust the figure height.
    # Let's use a dynamic step that fits the data into the 0.9 -> 0.05 vertical space
    row_count = len(df.head(limit))
    if row_count > 0:
        step_size = 0.85 / (row_count + 1) 
    else:
        step_size = 0.1

    y_pos = y_start
    for _, row in df.head(limit).iterrows():
        # Prepare basic strings
        name_str = str(row['uma_name'])
        epithet_str = str(row['epithet']) if pd.notna(row['epithet']) else '-'
        team_str = str(row['team'])
        max_str = f"{int(row['max_score']):,}"
        avg_str = f"{int(row['avg_score']):,}"
        p95_str = f"{int(row['p95_score']):,}"

        current_col = 0
        
        # 1. Trainer (Optional)
        if show_trainer:
            trainer_str = str(row.get('trainer_name', '-'))
            # Truncate if too long
            if len(trainer_str) > 12: trainer_str = trainer_str[:11] + ".."
            ax.text(header_positions[current_col], y_pos, trainer_str, color='#FFAB91', fontsize=12, transform=ax.transAxes, va='top', ha='left')
            current_col += 1

        # 2. Name
        ax.text(header_positions[current_col], y_pos, name_str, color='#E0E0E0', fontsize=12, transform=ax.transAxes, va='top', ha='left')
        current_col += 1
        
        # 3. Epithet
        ax.text(header_positions[current_col], y_pos, epithet_str, color='#BDBDBD', fontsize=11, transform=ax.transAxes, va='top', ha='left')
        current_col += 1
        
        # 4. Team
        ax.text(header_positions[current_col], y_pos, team_str, color='#E0E0E0', fontsize=12, transform=ax.transAxes, va='top', ha='left')
        current_col += 1
        
        # 5. Max
        ax.text(header_positions[current_col], y_pos, max_str, color='#FFD700', fontsize=12, weight='bold', transform=ax.transAxes, va='top', ha='left')
        current_col += 1
        
        # 6. Avg
        ax.text(header_positions[current_col], y_pos, avg_str, color='#E0E0E0', fontsize=12, transform=ax.transAxes, va='top', ha='left')
        current_col += 1
        
        # 7. P95
        ax.text(header_positions[current_col], y_pos, p95_str, color='#64B5F6', fontsize=12, transform=ax.transAxes, va='top', ha='left')

        y_pos -= step_size

    _add_timestamps_to_fig(fig, f"{len(df)} Total Umas")
    ax.axis('off')

    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            filepath = tmp_file.name
        fig.savefig(filepath, bbox_inches='tight', pad_inches=0.3, facecolor=fig.get_facecolor())
        return filepath
    except Exception as e:
        logger.error(f"Failed to save image: {e}")
        return None

def generate_team_summary_image(df: pd.DataFrame, title: str) -> str:
    logger.info(f"Generating team summary image for: {title}")
    if df.empty:
        df = pd.DataFrame(columns=['team', 'AvgTeamBest', 'MedianTeamBest', 'P95TeamBest'])
        
    limit = 10
    
    # --- SPACING FIX ---
    # More generous height calculation
    fig_height = 2 + (len(df.head(limit)) * 0.5)
    fig_height = max(4, min(12, fig_height))
    
    fig = Figure(figsize=(12, fig_height))
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)

    fig.patch.set_facecolor('#2E2E2E')
    ax.set_facecolor('#2E2E2E')
    ax.set_title(title, color='white', loc='left', pad=20, fontsize=16, weight='bold')

    headers = ['Team', 'Avg Team Best', 'Median Team Best', 'P95 Team Best']
    header_positions = [0.01, 0.30, 0.55, 0.80]
    
    for i, header in enumerate(headers):
        ax.text(header_positions[i], 0.92, header, color='#A0A0A0', fontsize=10, weight='bold', transform=ax.transAxes, va='top', ha='left')

    # Dynamic spacing
    row_count = len(df.head(limit))
    if row_count > 0:
        step_size = 0.80 / (row_count + 1) 
    else:
        step_size = 0.1

    y_pos = 0.88
    for _, row in df.head(limit).iterrows():
        team_str = str(row['team'])
        avg_str = f"{int(row['AvgTeamBest']):,}"
        median_str = f"{int(row['MedianTeamBest']):,}"
        p95_str = f"{int(row['P95TeamBest']):,}"

        ax.text(header_positions[0], y_pos, team_str, color='#E0E0E0', fontsize=12, transform=ax.transAxes, va='top', ha='left')
        ax.text(header_positions[1], y_pos, avg_str, color='#FFD700', fontsize=12, weight='bold', transform=ax.transAxes, va='top', ha='left')
        ax.text(header_positions[2], y_pos, median_str, color='#E0E0E0', fontsize=12, transform=ax.transAxes, va='top', ha='left')
        ax.text(header_positions[3], y_pos, p95_str, color='#64B5F6', fontsize=12, transform=ax.transAxes, va='top', ha='left')

        y_pos -= step_size

    _add_timestamps_to_fig(fig, f"{len(df)} Total Teams")
    ax.axis('off')

    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            filepath = tmp_file.name
        fig.savefig(filepath, bbox_inches='tight', pad_inches=0.3, facecolor=fig.get_facecolor())
        return filepath
    except Exception as e:
        logger.error(f"Failed to save image: {e}")
        return None