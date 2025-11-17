# trackmaster/core/validation.py

from thefuzz import process as fuzzy_process
from dataclasses import dataclass, field
from typing import List, Dict, Any

# TODO: Move this to a DB table or a flat file (e.g., umas.json)
# For now, a set is fine.
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

class ValidationService:
    def __init__(self, db_manager): # db_manager isn't used yet, but will be
        self.db_manager = db_manager
        # In the future, you could load VALID_UMA_NAMES from the DB
        self.valid_names = VALID_UMA_NAMES
        self.confidence_threshold = 85 # Tune this value

    async def validate_and_correct(self, ocr_scores: List[Dict[str, Any]]) -> ValidationResult:
        """
        Loops through OCR'd scores, validates names, and auto-corrects.
        """
        corrected_scores = []
        low_confidence_count = 0
        was_auto_corrected = False
        
        for uma in ocr_scores:
            extracted_name = uma.get("name", "UNKNOWN")
            
            if extracted_name in self.valid_names:
                # Perfect match
                corrected_scores.append(uma)
            else:
                # Fuzzy match
                best_match, confidence = fuzzy_process.extractOne(extracted_name, self.valid_names)
                
                if confidence >= self.confidence_threshold:
                    # Auto-correct with high confidence
                    uma["name"] = best_match
                    uma["original_ocr_name"] = extracted_name # Keep for the modal
                    corrected_scores.append(uma)
                    was_auto_corrected = True
                else:
                    # Low confidence, flag for review
                    uma["name"] = extracted_name # Keep the bad name for now
                    low_confidence_count += 1
                    corrected_scores.append(uma)

        return ValidationResult(
            corrected_scores=corrected_scores,
            low_confidence_count=low_confidence_count,
            was_auto_corrected=was_auto_corrected
        )