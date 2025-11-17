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
            prompt = """Your task is to extract all character scores from the provided Umamusume "Score Info" screenshot.
The image contains a list of characters. For each character, find these four pieces of text:
1.  The **Epithet**: Text in a small banner (e.g., "Dream Team", "Finals Champion").
2.  The **Name**: The main, larger text (e.g., "Maruzensky", "Sakura Bakushin O").
3.  The **Team**: The text on the circular icon (e.g., "Mile", "Sprint", "Dirt", "Medium", "Long").
4.  The **Score**: The number followed by "pts" (e.g., "46,730 pts").

Return the data as a single, valid JSON object with one key: "uma_scores".
The "uma_scores" array must include an object for **every character** visible in the screenshot.

Follow these rules exactly:
- "name": Must be a string (the main, larger text).
- "epithet": Must be a string (the text from the banner). If there is no epithet, use null.
- "team": Must be a string from the circular icon.
- "score": Must be a **number**. Remove commas and the " pts" suffix.

Here is a perfect example of the required output format. The example is for format only, not a complete list.
{
  "uma_scores": [
    { "name": "Maruzensky", "epithet": "Dream Team", "team": "Mile", "score": 46730 },
    { "name": "Sakura Bakushin O", "epithet": "Finals Champion", "team": "Sprint", "score": 42638 },
    { "name": "Daiwa Scarlet", "epithet": "Dream Team", "team": "Mile", "score": 41461 }
  ]
}

Return ONLY the JSON object and nothing else.
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