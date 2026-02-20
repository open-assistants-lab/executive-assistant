"""Executive Assistant - Main CLI entry point."""

import argparse
import sys

# Load environment variables
from dotenv import load_dotenv

load_dotenv()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(prog="ea", description="Executive Assistant")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # CLI command
    subparsers.add_parser("cli", help="Start interactive CLI")

    # HTTP command
    subparsers.add_parser("http", help="Start HTTP server")

    # Telegram command
    subparsers.add_parser("telegram", help="Start Telegram bot")

    args = parser.parse_args()

    if args.command == "cli" or args.command is None:
        from src.cli.main import main as cli_main

        cli_main()
    elif args.command == "http":
        from src.http.main import run as http_run

        http_run()
    elif args.command == "telegram":
        import asyncio
        from src.telegram.main import main as telegram_main

        asyncio.run(telegram_main())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
