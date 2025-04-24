import os
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class MongoDBClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            logger.debug("Creating new MongoDBClient instance.")
            cls._instance = super(MongoDBClient, cls).__new__(cls)
            cls._instance._initialized = False
        else:
            logger.debug("Returning existing MongoDBClient instance.")
        return cls._instance

    def __init__(self, uri: str):
        if hasattr(self, '_initialized') and self._initialized:
            logger.debug("MongoDBClient already initialized, skipping __init__.")
            return

        logger.debug(f"Initializing MongoDBClient with URI ending in ...{uri[-10:] if uri else 'None'}")
        if not uri:
            logger.critical("MongoDBClient initialized without a URI.")
            raise ValueError("MONGO_URI was not provided to MongoDBClient constructor.")

        try:
            self.client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000) 

            logger.info("Motor AsyncIOMotorClient created.")
            self.db = self.client['scriptly_db']
            self.config_col = self.db['guild_config']
            self._initialized = True 
            logger.info("MongoDB Client Initialized successfully.")
        except Exception as e:
            logger.exception(f"Failed to initialize MongoDB connection or client: {e}")

            self._initialized = False 
            raise ConnectionError(f"Failed to connect to MongoDB: {e}") from e


    async def load_all_configs(self) -> Dict[int, Optional[List[int]]]:
        if not self._initialized:
             logger.error("Attempted to load configs while DB client not initialized.")
             return {}
        configs = {}
        try:
            cursor = self.config_col.find({})
            async for doc in cursor:
                guild_id = doc.get('guild_id')
                if guild_id:
                    is_restricted = doc.get('is_restricted', False)
                    allowed_channels_db = doc.get('allowed_channels')
                    if is_restricted:
                        configs[guild_id] = allowed_channels_db if isinstance(allowed_channels_db, list) else []
                    else:
                        configs[guild_id] = None
            count = len(configs)
            logger.info(f"MongoDB: Loaded configs for {count} guild(s).")
            return configs
        except Exception as e:
            logger.exception(f"Error loading guild configs from MongoDB: {e}")
            return {} 

    async def save_config(self, guild_id: int, is_restricted: bool, channels: Optional[List[int]]):
         if not self._initialized:
             logger.error("Attempted to save config while DB client not initialized.")
             return
         try:
            channels_to_save = channels if is_restricted else []

            await self.config_col.update_one(
                {'guild_id': guild_id},
                {'$set': {
                    'guild_id': guild_id,
                    'is_restricted': is_restricted,
                    'allowed_channels': channels_to_save 
                    }
                },
                upsert=True
            )
            logger.info(f"Saved config for guild {guild_id}. Restricted: {is_restricted}, Channels: {channels_to_save if is_restricted else 'N/A'}")
         except Exception as e:
            logger.exception(f"Error saving config for guild {guild_id} to MongoDB: {e}")


_db_client_instance: Optional[MongoDBClient] = None

async def get_db_client() -> MongoDBClient:
    global _db_client_instance
    if _db_client_instance is None or not _db_client_instance._initialized:
        logger.info("DB client instance not available or not initialized, attempting to create...")
        mongo_uri_from_env = os.getenv("MONGO_URI")
        logger.debug(f"Value of os.getenv('MONGO_URI') in get_db_client = '{mongo_uri_from_env}'")
        if not mongo_uri_from_env:
            logger.critical("MONGO_URI environment variable was None/empty when get_db_client() needed to create instance.")
            raise ValueError("MONGO_URI environment variable is required but was not found.")

        try:
            _db_client_instance = MongoDBClient(uri=mongo_uri_from_env)
            await _db_client_instance.client.admin.command('ping')
            logger.info("MongoDB connection confirmed with ping.")
        except ConnectionError as ce:
             logger.critical(f"MongoDB connection failed during initial ping check: {ce}", exc_info=True)
             _db_client_instance = None
             raise
        except Exception as e:
             logger.critical(f"Failed to create MongoDBClient instance: {e}", exc_info=True)
             _db_client_instance = None
             raise

    if _db_client_instance and _db_client_instance._initialized:
        return _db_client_instance
    else:
        logger.error("Failed to get a valid DB client instance.")
        raise RuntimeError("Could not retrieve a valid database client instance.")