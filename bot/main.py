import os
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder
from vision30x.bot.scheduler import setup_jobs
from vision30x.bot.handlers import setup_handlers

# Load .env from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN not set in .env")

    app = ApplicationBuilder().token(token).build()
    setup_handlers(app)
    setup_jobs(app)

    print("✅ 30x_assistant is running. Press CTRL+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
