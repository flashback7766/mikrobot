#!/usr/bin/env python3
"""
Cross-platform setup script for MikroBot
Works on Windows, Linux, and macOS
"""

import os
import sys
import subprocess
from pathlib import Path

def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")

def print_step(icon, text):
    print(f"{icon} {text}")

def main():
    print_header("MikroBot Extended — Setup")
    
    # Check if .env exists
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print_step("✓", "Found existing .env file")
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'BOT_TOKEN' in content and 'PUT_TOKEN_HERE' not in content:
                print_step("✓", "Bot token already configured")
                token_configured = True
            else:
                token_configured = False
    else:
        if not env_example.exists():
            print_step("❌", ".env.example not found!")
            print("\nPlease run this script from the mikrobot_extended directory")
            sys.exit(1)
        
        print_step("⏳", "Creating .env from template...")
        with open(env_example, 'r', encoding='utf-8') as f:
            template = f.read()
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(template)
        print_step("✓", "Created .env file")
        token_configured = False
    
    # Get bot token
    if not token_configured:
        print("\n⚠️  IMPORTANT: Get your bot token from https://t.me/BotFather")
        print("\nTo get a token:")
        print("  1. Open Telegram")
        print("  2. Message @BotFather")
        print("  3. Send: /newbot (or /mybots for existing)")
        print("  4. Copy the token\n")
        
        token = input("Enter your bot token (or press Enter to skip): ").strip()
        
        if token and token != "PUT_TOKEN_HERE":
            # Read current .env
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Update BOT_TOKEN line
            with open(env_file, 'w', encoding='utf-8') as f:
                for line in lines:
                    if line.strip().startswith('BOT_TOKEN='):
                        f.write(f'BOT_TOKEN={token}\n')
                    else:
                        f.write(line)
            
            print_step("✓", "Token saved to .env")
            token_configured = True
        else:
            print_step("⚠️", "Skipped token setup - you'll need to edit .env manually")
    
    # Check Python version
    print_step("⏳", "Checking Python version...")
    py_version = sys.version_info
    print_step("✓", f"Python {py_version.major}.{py_version.minor} detected")
    
    if py_version < (3, 9):
        print_step("⚠️", "Python 3.9+ recommended")
    
    # Install dependencies
    print_step("⏳", "Installing dependencies...")
    try:
        # Try without --break-system-packages first
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print_step("✓", "Dependencies installed")
        else:
            # Try with --break-system-packages
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", 
                 "--break-system-packages", "--quiet"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print_step("✓", "Dependencies installed")
            else:
                print_step("⚠️", "Failed to install dependencies automatically")
                print("\nPlease run manually:")
                print(f"  {sys.executable} -m pip install -r requirements.txt")
    except Exception as e:
        print_step("⚠️", f"Error installing dependencies: {e}")
        print("\nPlease run manually:")
        print(f"  {sys.executable} -m pip install -r requirements.txt")
    
    # Create data directory
    data_dir = Path("data")
    if not data_dir.exists():
        data_dir.mkdir()
        print_step("✓", "Created data directory")
    
    # Final status
    print_header("Setup Complete!")
    
    if not token_configured:
        print("⚠️  WARNING: BOT_TOKEN not configured!")
        print("\nNext steps:")
        print("  1. Edit .env file")
        print("  2. Set BOT_TOKEN=your_token_here")
        print("  3. Get token from @BotFather in Telegram")
        print(f"  4. Run: {sys.executable} test_token.py")
        print(f"  5. Then: {sys.executable} bot.py")
    else:
        print("✓ Bot token configured")
        print("\nReady to start!")
        print("\nNext steps:")
        print(f"  1. Test token: {sys.executable} test_token.py")
        print(f"  2. Start bot:  {sys.executable} bot.py")
        
        # Ask if they want to start now
        if sys.stdin.isatty():  # Only ask if interactive
            response = input("\nStart the bot now? (y/n): ").lower().strip()
            if response in ('y', 'yes'):
                print("\nStarting MikroBot...")
                print("Press Ctrl+C to stop\n")
                try:
                    subprocess.run([sys.executable, "bot.py"])
                except KeyboardInterrupt:
                    print("\n\n⏹ Bot stopped")
                except Exception as e:
                    print(f"\n❌ Error: {e}")
    
    print("\nFor help, see the README or join the support group: https://t.me/mikrobot_support\n\n\n\n\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹ Setup cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
