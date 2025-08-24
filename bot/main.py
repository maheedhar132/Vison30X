# bot/main.py
import os
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

from bot.handlers import setup_handlers
from bot.scheduler import setup_jobs
from bot.db import init_db
from bot.reminders import setup_reminders  # if you added reminders

def main():
    load_dotenv(Path(__file__).parent.parent / ".env")

    # init AFTER env is loaded
    init_db()

    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN missing in .env")

    app = ApplicationBuilder().token(token).build()

    setup_handlers(app)
    setup_jobs(app)
    setup_reminders(app)

    print("✅ Vison30X Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
