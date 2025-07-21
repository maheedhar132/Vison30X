from apscheduler.schedulers.background import BackgroundScheduler
from bot.utils import send_manifestation
from datetime import time

def setup_jobs(app):
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    scheduler.add_job(send_manifestation, 'cron', hour=9, minute=0, args=[app, 0])
    scheduler.add_job(send_manifestation, 'cron', hour=9, minute=15, args=[app, 1])
    scheduler.add_job(send_manifestation, 'cron', hour=9, minute=30, args=[app, 2])

    scheduler.start()
