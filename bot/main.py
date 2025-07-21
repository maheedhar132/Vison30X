import os
from telegram.ext import ApplicationBuilder
from bot.scheduler import setup_jobs
from dotenv import load_dotenv

load_dotenv()

def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    setup_jobs(app)
    app.run_polling()

if __name__ == "__main__":
    main()
