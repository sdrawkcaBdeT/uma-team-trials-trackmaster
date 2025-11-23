# trackmaster/core/validation.py

from thefuzz import process as fuzzy_process
from dataclasses import dataclass, field
from typing import List, Dict, Any
import asyncio

# TODO: Move this to a DB table or a flat file (e.g., umas.json)
# For now, a set is fine.

# Define valid teams to detect swaps
VALID_TEAMS = {"Sprint", "Mile", "Medium", "Long", "Dirt"}

VALID_UMA_NAMES = {
    "King Halo",
    "Nice Nature",
    "Matikanefukukitaru",
    "Haru Urara",
    "Sakura Bakushin O",
    "Winning Ticket",
    "Agnes Tachyon",
    "Mejiro Ryan",
    "Super Creek",
    "Mayano Top Gun",
    "Air Groove",
    "El Condor Pasa",
    "Grass Wonder",
    "Daiwa Scarlet",
    "Vodka",
    "Gold Ship",
    "Rice Shower",
    "Symboli Rudolf",
    "Mejiro McQueen",
    "Taiki Shuttle",
    "Oguri Cap",
    "Maruzensky",
    "Tokai Teio",
    "Silence Suzuka",
    "Special Week",
    "TM Opera O",
    "Mihono Bourbon",
    "Biwa Hayahide",
    # "Mejiro McQueen" Anime
    #"Tokai Teio (Anime)",
    "Curren Chan",
    "Narita Taishin",
    "Smart Falcon",
    "Narita Brian",
    # "Mayano Top Gun (Wedding)",
    # "Air Groove (Wedding)",
    "Seiun Sky",
    "Hishi Amazon",
    # "El Condor Pasa (Fantasy)",
    # "Grass Wonder (Fantasy)",
    "Fuji Kiseki",
    "Gold City",
    # "Maruzensky (Summer)",
    # "Special Week (Summer)",
    "Meisho Doto",
    "Eishin Flash",
    # "Matikanefukukitaru (Full Armor)",
    "Hishi Akebono",
    "Agnes Digital",
    # "Super Creek (Halloween)",
    # "Rice Shower (Halloween)",
    "Kawakami Princess",
    "Manhattan Cafe",
    # "Gold City (Festival)",
    # "Symboli Rudolf (Festival)",
    "Tosen Jordan",
    "Mejiro Dober",
    "Fine Motion",
    "Tamamo Cross",
    "Sakura Chiyono O",
    "Mejiro Ardan",
    "Admire Vega",
    "Kitasan Black",
    # etc
}

@dataclass
class ValidationResult:
    corrected_scores: List[Dict[str, Any]]
    low_confidence_count: int = 0
    was_auto_corrected: bool = False

def _run_validation_sync(ocr_scores: List[Dict[str, Any]], valid_names: set, confidence_threshold: int) -> ValidationResult:
    corrected_scores = []
    low_confidence_count = 0
    was_auto_corrected = False
    
    for uma in ocr_scores:
        extracted_name = uma.get("name", "UNKNOWN").strip()
        extracted_team = uma.get("team", "UNKNOWN").strip()
        
        # --- FIX: DETECT SWAPPED FIELDS ---
        # If the Name looks like a Team, and the Team looks like a Name, swap them.
        if extracted_name in VALID_TEAMS and extracted_team not in VALID_TEAMS:
            # Check if the "team" is actually a valid name
            swap_check, swap_conf = fuzzy_process.extractOne(extracted_team, valid_names)
            if swap_conf > 80:
                # Confirmed swap
                temp = extracted_name
                extracted_name = extracted_team
                extracted_team = temp
                uma["team"] = extracted_team
                was_auto_corrected = True

        # --- EXISTING NAME VALIDATION ---
        if extracted_name in valid_names:
            uma["name"] = extracted_name
            corrected_scores.append(uma)
        else:
            best_match, confidence = fuzzy_process.extractOne(extracted_name, valid_names)
            
            if confidence >= confidence_threshold:
                uma["name"] = best_match
                uma["original_ocr_name"] = extracted_name
                corrected_scores.append(uma)
                was_auto_corrected = True
            else:
                uma["name"] = extracted_name
                low_confidence_count += 1
                corrected_scores.append(uma)

    return ValidationResult(
        corrected_scores=corrected_scores,
        low_confidence_count=low_confidence_count,
        was_auto_corrected=was_auto_corrected
    )

class ValidationService:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.valid_names = VALID_UMA_NAMES
        self.confidence_threshold = 85

    async def validate_and_correct(self, ocr_scores: List[Dict[str, Any]]) -> ValidationResult:
        return await asyncio.to_thread(
            _run_validation_sync,
            ocr_scores,
            self.valid_names,
            self.confidence_threshold
        )