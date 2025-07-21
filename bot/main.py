from telegram.ext import ApplicationBuilder
from dotenv import load_dotenv
from bot.scheduler import setup_jobs
from bot.handlers import start, health, status
from telegram.ext import CommandHandler
import os

load_dotenv()

def setup_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health))
    app.add_handler(CommandHandler("status", status))

def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    setup_handlers(app)
    setup_jobs(app)
    app.run_polling()

if __name__ == "__main__":
    main()
