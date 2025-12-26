# bot/main.py
import os
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

from bot.handlers import setup_handlers
from bot.scheduler import setup_jobs
from bot.db import init_db


def main():
    # Load env
    load_dotenv(Path(__file__).parent.parent / ".env")

    # Init persistence (minimal state only)
    init_db()

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN missing in .env")

    app = ApplicationBuilder().token(token).build()

    # Register handlers
    setup_handlers(app)

    # Schedule daily jobs (manifestations + cards)
    setup_jobs(app)

    print("✅ Vison30X Bot running (Manifestations + Cards)")
    app.run_polling()


if __name__ == "__main__":
    main()
