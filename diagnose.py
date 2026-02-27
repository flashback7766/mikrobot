#!/usr/bin/env python3
"""
Diagnostic script to check MikroBot configuration
"""

import os
import sys
from pathlib import Path

print("=" * 70)
print("  MikroBot Configuration Diagnostic")
print("=" * 70)
print()

# Check .env file exists
env_file = Path(".env")
if not env_file.exists():
    print("❌ .env file NOT FOUND")
    print("   Create it with: cp .env.example .env")
    sys.exit(1)
else:
    print("✅ .env file exists")

# Check .env contents
print("\n📄 .env file contents:")
with open(".env") as f:
    lines = f.readlines()
    for line in lines:
        line = line.strip()
        if line.startswith("BOT_TOKEN"):
            # Mask the token for security
            parts = line.split("=", 1)
            if len(parts) == 2 and parts[1] and parts[1] != "PUT_TOKEN_HERE":
                token = parts[1].strip()
                # Show first 10 and last 5 characters
                masked = f"{token[:10]}...{token[-5:]}" if len(token) > 15 else "***"
                print(f"   BOT_TOKEN = {masked}")
                print(f"   Token length: {len(token)} chars")
                
                # Validate token format
                if ":" not in token:
                    print("   ❌ INVALID: Token must contain ':' character")
                    print("   Format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
                else:
                    bot_id, bot_secret = token.split(":", 1)
                    if not bot_id.isdigit():
                        print(f"   ❌ INVALID: Bot ID must be numeric (got: {bot_id})")
                    elif len(bot_secret) < 20:
                        print(f"   ❌ INVALID: Secret too short (got {len(bot_secret)} chars)")
                    else:
                        print("   ✅ Token format looks valid")
            else:
                print("   ❌ BOT_TOKEN is empty or set to PUT_TOKEN_HERE")
        elif line.startswith("OWNER_ID"):
            print(f"   {line}")
        elif line.startswith("LOG_LEVEL"):
            print(f"   {line}")

# Try loading with python-dotenv
print("\n🔍 Testing python-dotenv loading...")
try:
    from dotenv import load_dotenv
    load_dotenv()
    token_from_env = os.environ.get("BOT_TOKEN")
    if token_from_env and token_from_env != "PUT_TOKEN_HERE":
        print(f"   ✅ Token loaded: {token_from_env[:10]}...{token_from_env[-5:]}")
    else:
        print(f"   ❌ Token not loaded or invalid: {token_from_env}")
except ImportError:
    print("   ⚠️  python-dotenv not installed")

# Try loading config.py
print("\n🔧 Testing config.py...")
try:
    import config
    if config.BOT_TOKEN and config.BOT_TOKEN != "PUT_TOKEN_HERE":
        print(f"   ✅ config.BOT_TOKEN loaded: {config.BOT_TOKEN[:10]}...{config.BOT_TOKEN[-5:]}")
    else:
        print(f"   ❌ config.BOT_TOKEN invalid: {config.BOT_TOKEN}")
except Exception as e:
    print(f"   ❌ Error loading config: {e}")

print("\n" + "=" * 70)
print("  Recommendations:")
print("=" * 70)

print("""
1. Get a NEW token from @BotFather:
   • Open Telegram
   • Message @BotFather
   • If you already have a bot:
     - Send: /mybots
     - Select your bot
     - API Token → Copy
   • If you need a new bot:
     - Send: /newbot
     - Follow prompts
     - Copy the token

2. Update .env file:
   • Edit .env
   • Replace BOT_TOKEN value with your new token
   • Make sure no extra spaces or quotes

3. Test the token:
   • Run: python3 test_token.py
   • Or just run: python3 bot.py

Common issues:
• Token was revoked in @BotFather
• Extra spaces around the token in .env
• Quotes around the token (don't use quotes)
• Wrong file (.env vs .env.example)
""")
