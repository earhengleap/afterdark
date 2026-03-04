"""
Migration script to import legacy users/*.json flat files into the SQLite database.
"""
import os
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import history_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MigrateUsers")

def migrate_users_to_db():
    users_dir = Path("users")
    if not users_dir.exists():
        logger.info("No users/ directory found. Nothing to migrate.")
        return

    json_files = list(users_dir.glob("*.json"))
    if not json_files:
        logger.info("No .json files found in users/. Nothing to migrate.")
        return

    total_migrated = 0
    
    for file_path in json_files:
        try:
            user_id = int(file_path.stem)
        except ValueError:
            logger.warning(f"Skipping non-integer file: {file_path}")
            continue
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                history = json.load(f)
                
            for entry in history:
                history_db.add_entry(
                    user_id=user_id,
                    url=entry.get("url", ""),
                    source_username=entry.get("username", "unknown"),
                    filename=None,
                    status=entry.get("status", "unknown"),
                    content_type=entry.get("content_type", "unknown")
                )
            
            logger.info(f"Migrated {len(history)} entries for user {user_id}")
            total_migrated += len(history)
            
        except Exception as e:
            logger.error(f"Error migrating {file_path}: {e}")
            
    logger.info(f"Successfully migrated {total_migrated} legacy history items to SQLite.")

if __name__ == "__main__":
    migrate_users_to_db()
