# main.py

import asyncio
import logging
from trackmaster.config import settings
from trackmaster.bot import TrackmasterBot
from trackmaster.core.ocr_processor import apply_ocr_patch

# Set up logging
logging.basicConfig(level=logging.INFO)

async def main():
    # Apply custom prompt *before* we do anything else
    apply_ocr_patch()
    
    if not settings.DISCORD_BOT_TOKEN:
        logging.error("CRITICAL: DISCORD_BOT_TOKEN not found in .env file.")
        return

    bot = TrackmasterBot()
    
    try:
        await bot.start(settings.DISCORD_BOT_TOKEN)
    except KeyboardInterrupt:
        await bot.close()
    except Exception as e:
        logging.error(f"Bot loop encountered an error: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    asyncio.run(main())