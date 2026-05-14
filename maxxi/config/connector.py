# type: ignore

import argparse
import asyncio
import logging
import os

from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_ID = int(os.getenv('TELEGRAM_API_ID', '0'))
API_HASH = os.getenv('TELEGRAM_API_HASH', 'YOUR_API_HASH')
SESSION_NAME = os.getenv("TELEGRAM_SESSION_FILE", "telegram_blob_session")
SESSION_STRING = os.getenv("TELEGRAM_SESSION_STRING", "")


async def authorize_telegram(force_new: bool = False):
    if not API_ID or API_HASH == 'YOUR_API_HASH':
        logger.error("Please set TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables or replace placeholders in auth_cli.py")
        return

    session = StringSession("") if force_new else StringSession(SESSION_STRING) if SESSION_STRING else SESSION_NAME
    client = TelegramClient(
        session,
        API_ID,
        API_HASH,
    )

    logger.info("Connecting to Telegram...")
    await client.connect()

    if not await client.is_user_authorized():
        logger.info("Client not authorized. Starting authorization flow.")
        try:
            await client.start(phone=lambda: input("Please enter your phone number (e.g., +12345678900): "),
                               code_callback=lambda: input("Please enter the code you received: "),
                               password=lambda: input("Please enter your 2FA password (if any): "))
            logger.info("Authorization successful!")
        except Exception as e:
            logger.error(f"Error during authorization: {e}")
    else:
        logger.info("Client already authorized.")

    session = StringSession.save(client.session)
    if session:
        logger.info("Set this as TELEGRAM_SESSION_STRING:")
        print(session)

    await client.disconnect()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Authorize Telegram and print a StringSession.")
    parser.add_argument(
        "--new",
        action="store_true",
        help="Ignore existing session env/file and create a fresh StringSession.",
    )
    args = parser.parse_args()
    asyncio.run(authorize_telegram(force_new=args.new))
