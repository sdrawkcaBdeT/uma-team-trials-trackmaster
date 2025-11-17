# trackmaster/core/utils.py
import datetime

# --- YOUR GAME'S RESET TIME (in UTC) ---
# 0 = Monday, 1 = Tuesday, ... 6 = Sunday
GAME_RESET_DAY_OF_WEEK = 0  
GAME_RESET_HOUR_UTC = 9
# ---------------------------------------

def get_current_season_id(timestamp: datetime.datetime) -> str:
    """
    Calculates the "season" (run_week) based on the game's specific
    weekly reset time, not the calendar week.
    """
    # Adjust timestamp to be "on" the reset day
    days_since_reset = (timestamp.weekday() - GAME_RESET_DAY_OF_WEEK) % 7
    
    # Check if we are on the reset day, but *before* the reset hour
    if days_since_reset == 0 and timestamp.hour < GAME_RESET_HOUR_UTC:
        # We are still in the *previous* week's season
        # Go back 7 days to get the previous week's date
        most_recent_reset_date = timestamp.date() - datetime.timedelta(days=7)
    else:
        # We are in the *current* week's season
        # Go back to the most recent reset day
        most_recent_reset_date = timestamp.date() - datetime.timedelta(days=days_since_reset)
    
    # Use the date of that reset's week (Monday-based)
    return most_recent_reset_date.strftime("%Y-W%W")