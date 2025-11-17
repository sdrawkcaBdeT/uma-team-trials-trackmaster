# trackmaster/bot.py

import discord
from discord.ext import commands
import logging
import asyncio # We need this for to_thread
from trackmaster.config import settings
from trackmaster.core.database import DatabaseManager # <-- Our new class
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
        
        # 1. Initialize Database
        try:
            self.db_manager = DatabaseManager()
            # Run the synchronous init function in a separate thread
            # await asyncio.to_thread(self.db_manager.initialize_database) # <--- COMMENTED OUT
            # logger.info("Database initialized successfully.") # <--- COMMENTED OUT
            logger.info("Database connection pool created.") # <-- More accurate log
        except Exception as e:
            # We still want to catch errors from the POOL creation
            logger.critical(f"Failed to create database connection pool: {e}") 
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
        if self.db_manager:
            self.db_manager.close_all() # <-- Call the sync close method
            logger.info("Database connection pool closed.")
        await super().close()