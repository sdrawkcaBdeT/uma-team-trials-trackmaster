# trackmaster/core/ocr_processor.py

import logging
from PIL import Image

# 1. Import the ORIGINAL classes and the module we need to patch
from docstrange.pipeline.nanonets_processor import NanonetsDocumentProcessor
import docstrange.pipeline.ocr_service as ocr_service_module # The module to patch
from docstrange.pipeline.ocr_service import NanonetsOCRService
from docstrange.extractor import DocumentExtractor

logger = logging.getLogger(__name__)

# 2. Define our NEW class that inherits from the original
class CustomNanonetsProcessor(NanonetsDocumentProcessor):
    """
    A custom processor that overrides the prompt for Umamusume data extraction.
    """
    
    # 3. Override ONLY the one method we care about.
    def _extract_text_with_nanonets(self, image_path: str, max_new_tokens: int = 4096) -> str:
        """Extract text using Nanonets OCR model with our custom prompt."""
        try:
            # --- THIS IS OUR CUSTOM PROMPT ---
            prompt = """You are a data entry engine extracting high scores from a video game screenshot.
            
VISUAL STRUCTURE:
The image contains exactly 5 rows of character data. 
You MUST extract exactly 5 objects. Do not stop until you have 5.

For each row, find these fields:
1. **Name**: The largest text (e.g. "Special Week"). NOTE: "Mile", "Sprint", "Long" are TEAMS, not names.
2. **Team**: Text inside the circular icon (e.g. "Mile", "Sprint", "Dirt").
3. **Epithet**: Small banner text above the name. If missing, use null.
4. **Score**: The number ending in "pts".

OUTPUT FORMAT:
Return a single JSON object with key "uma_scores", which is a list of objects.

Example JSON structure:
{
  "uma_scores": [
    { "name": "Maruzensky", "epithet": "Dream Team", "team": "Mile", "score": 46730 },
    ... (3 more items) ...
    { "name": "Oguri Cap", "epithet": null, "team": "Dirt", "score": 38200 }
  ]
}

CRITICAL RULES:
1. Do not hallucinate.
2. Do not omit the last row. There are 5 rows.
3. Remove commas from scores.
4. Output ONLY valid JSON.
"""
            # --- END OF CUSTOM PROMPT ---
            
            image = Image.open(image_path)
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": [
                    {"type": "image", "image": f"file://{image_path}"},
                    {"type": "text", "text": prompt},
                ]},
            ]
            
            # This logic is copied from the original docstrange file
            text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self.processor(text=[text], images=[image], padding=True, return_tensors="pt")
            inputs = inputs.to(self.model.device)
            
            output_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
            generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs.input_ids, output_ids)]
            
            output_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True, clean_up_tokenization_spaces=True)
            return output_text[0]
            
        except Exception as e:
            logger.error(f"Nanonets OCR extraction failed: {e}")
            return ""

# 4.need to create a custom Service that *uses* new processor
class CustomNanonetsOCRService(NanonetsOCRService):
    def __init__(self):
        """Initialize the service."""
        # key change: it now creates custom processor
        self._processor = CustomNanonetsProcessor() 
        logger.info("CustomNanonetsOCRService initialized")

# 5. This is the function that does the "patching"
def apply_ocr_patch():
    """
    Monkey-patches the docstrange library to use our custom OCR processor.
    This MUST be called *before* DocumentExtractor is initialized.
    """
    logger.info("Applying custom Umamusume OCR patch...")
    
    # tell the ocr_service module to use our
    # custom service class instead of its original one.
    ocr_service_module.NanonetsOCRService = CustomNanonetsOCRService
    
    logger.info("Docstrange patched successfully.")

# 6. This is the setup function to call from your bot
def setup_local_extractor():
    """Initializes the DocumentExtractor."""
    print("Initializing the document extractor in local GPU mode...")
    try:
        extractor = DocumentExtractor(
            gpu=True,
            preserve_layout=True,
            ocr_enabled=True
        )
        print("Extractor initialized successfully.")
        return extractor
    except RuntimeError as e:
        print(f"CRITICAL ERROR: Could not initialize in GPU mode.")
        print(f"   Reason: {e}")
        return None