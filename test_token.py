#!/usr/bin/env python3
"""
Test if your Telegram bot token is valid
"""

import asyncio
import sys
import os

# Try to load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Get token
token = os.environ.get("BOT_TOKEN", "").strip()

if not token or token == "PUT_TOKEN_HERE":
    print("❌ BOT_TOKEN not set in .env file")
    print("\nPlease:")
    print("1. Edit .env file")
    print("2. Set BOT_TOKEN=your_actual_token_here")
    print("3. Get token from @BotFather in Telegram")
    sys.exit(1)

print(f"🔍 Testing token: {token[:10]}...{token[-5:]}")
print()

async def test_token():
    try:
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        
        bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        )
        
        print("⏳ Connecting to Telegram API...")
        me = await bot.get_me()
        
        print("=" * 70)
        print("✅ SUCCESS! Token is valid!")
        print("=" * 70)
        print(f"\nBot details:")
        print(f"  • Name: {me.first_name}")
        print(f"  • Username: @{me.username}")
        print(f"  • ID: {me.id}")
        print(f"  • Can join groups: {me.can_join_groups}")
        print(f"  • Can read messages: {me.can_read_all_group_messages}")
        print()
        print("✅ Your bot is ready to use!")
        print("\nNext steps:")
        print("  1. Run: python3 bot.py")
        print("  2. Open Telegram and message @" + me.username)
        print("  3. Send /start")
        print()
        
        await bot.session.close()
        return True
        
    except Exception as e:
        error_msg = str(e)
        
        print("=" * 70)
        print("❌ FAILED! Token is invalid")
        print("=" * 70)
        print(f"\nError: {error_msg}")
        print()
        
        if "Unauthorized" in error_msg:
            print("⚠️  This token has been revoked or is invalid.")
            print("\nTo fix:")
            print("  1. Open Telegram")
            print("  2. Message @BotFather")
            print("  3. Send: /mybots")
            print("  4. Select your bot")
            print("  5. Go to 'API Token'")
            print("  6. If revoked, you'll see 'Regenerate Token'")
            print("  7. Copy the new token")
            print("  8. Update .env file with new token")
            print()
            print("OR create a new bot:")
            print("  1. Message @BotFather")
            print("  2. Send: /newbot")
            print("  3. Follow prompts")
            print("  4. Copy the token")
            print("  5. Update .env file")
        
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_token())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⏹ Cancelled")
        sys.exit(1)
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("\nInstall with:")
        print("  pip3 install aiogram python-dotenv --break-system-packages")
        sys.exit(1)
