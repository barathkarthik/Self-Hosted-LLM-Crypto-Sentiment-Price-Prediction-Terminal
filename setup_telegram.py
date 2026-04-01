"""
One-time Telegram authentication.
Run this ONCE in your terminal — it will ask for your phone number and OTP.
After that, telegram.session is saved and main.py uses it silently forever.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH

session_path = os.path.join(os.path.dirname(__file__), "telegram.session")
print(f"API ID: {TELEGRAM_API_ID}")
print(f"Session path: {session_path}")
print()

# Use a persistent event loop — more reliable on Python 3.14
import asyncio
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from telethon import TelegramClient

client = TelegramClient(session_path, TELEGRAM_API_ID, TELEGRAM_API_HASH,
                        loop=loop)

async def auth():
    await client.start()
    me = await client.get_me()
    print(f"Logged in as: {me.first_name} (@{me.username})")

    print("\nTesting channel access...")
    count = 0
    async for msg in client.iter_messages("bitcoinnews", limit=3):
        if msg.text:
            print(f"  [{msg.date.strftime('%H:%M')}] {msg.text[:80]}")
            count += 1

    print(f"\nFetched {count} messages. Telegram is ready!")
    print("You can now run: python main.py --skip-history")
    await client.disconnect()

loop.run_until_complete(auth())
loop.close()
