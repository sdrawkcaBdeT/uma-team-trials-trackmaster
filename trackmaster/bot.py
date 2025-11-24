# trackmaster/bot.py

import discord
from discord.ext import commands
import logging
import asyncio # We need this for to_thread
from trackmaster.config import settings
from trackmaster.core.db import db_manager as session_manager # The low-level session manager
from trackmaster.core.database import DatabaseManager # The repository
from trackmaster.core.ocr_processor import setup_local_extractor

logger = logging.getLogger(__name__)

COGS_TO_LOAD = [
    "trackmaster.cogs.submission",
    "trackmaster.cogs.reporting",
    "trackmaster.cogs.help"
]

class TrackmasterBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

        self.db_manager: Optional[DatabaseManager] = None # <-- Stores our DB manager
        self.extractor = None

    async def setup_hook(self):
        """This runs once when the bot logs in."""
        
        # 1. Initialize Database Session Manager
        try:
            session_manager.init(host=settings.DB_HOST)
            self.db_manager = DatabaseManager()
            
            # Initialize tables (Async)
            await self.db_manager.initialize_database()
            logger.info("Database initialized and connected.")
        except Exception as e:
            logger.critical(f"Failed to connect to database: {e}") 
            await self.close()
            return    
        
        # 2. Initialize OCR Extractor
        self.extractor = setup_local_extractor()
        if self.extractor is None:
            logger.critical("Failed to initialize DocumentExtractor. Bot cannot start.")
            await self.close()
            return
            
        # 3. Load Cogs
        for cog in COGS_TO_LOAD:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}", exc_info=e)

        # 4. Sync slash commands
        logger.info("Syncing application commands...")
        synced_commands = await self.tree.sync()
        logger.info(f"Synced {len(synced_commands)} application commands.")

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info('Trackmaster is online.')

    async def close(self):
        """Clean up resources before shutting down."""
        await session_manager.close()
        await super().close()