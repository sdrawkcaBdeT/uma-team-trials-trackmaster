from thefuzz import process as fuzzy_process

VALID_UMA_NAMES = {
    "Maruzensky",
    "Sakura Bakushin O",
    "Daiwa Scarlet",
    "Special Week",
    "El Condor Pasa",
    "Oguri Cap",
    "Vodka",
    "Gold Ship",
    "Seiun Sky",
    "King Halo",
    "Symboli Rudolf",
    "Haru Urara",
    "Silence Suzuka",
    "Curren Chan",
    "Mejiro Ryan",
    # ...and every other Uma...
}



validated_scores = []
has_low_confidence_match = False

for uma in ocr_data["uma_scores"]:
    extracted_name = uma["name"]

    if extracted_name in VALID_UMA_NAMES:
        # Perfect match, high confidence!
        uma["name"] = extracted_name # Use the canonical name
        validated_scores.append(uma)
    else:
        # Not a perfect match. Let's find the closest.
        # fuzzy_process.extractOne returns (best_match, score_out_of_100)
        best_match, confidence = fuzzy_process.extractOne(extracted_name, VALID_UMA_NAMES)

        if confidence >= 85: # You can tune this threshold
            # High confidence "fuzzy" match.
            # e.g., OCR read "Maruzcnsky", fuzzy match returns ("Maruzensky", 92)
            print(f"Corrected '{extracted_name}' to '{best_match}' (Confidence: {confidence})")
            uma["name"] = best_match # Auto-correct the name
            validated_scores.append(uma)
        else:
            # Low confidence.
            # e.g., OCR read "XyzAbc", fuzzy returns ("Special Week", 40)
            # This is probably a cat photo or a major OCR fail.
            has_low_confidence_match = True
            uma["original_ocr"] = extracted_name # Keep the bad name for the "Edit" modal
            uma["name"] = best_match # Use the (bad) best guess
            validated_scores.append(uma)