from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from bot.manifestation import send_manifestation
from bot.cards import send_card_prompt, send_card_reveal

tz = timezone("Asia/Kolkata")

def setup_jobs(app):
    scheduler = BackgroundScheduler(timezone=tz)

    scheduler.add_job(send_manifestation, 'cron', hour=9, minute=0, args=[app, 0])
    scheduler.add_job(send_manifestation, 'cron', hour=9, minute=15, args=[app, 1])
    scheduler.add_job(send_manifestation, 'cron', hour=9, minute=30, args=[app, 2])
    scheduler.add_job(send_card_prompt, 'cron', hour=10, minute=0, args=[app])
    scheduler.add_job(send_card_reveal, 'cron', hour=19, minute=0, args=[app])

    scheduler.start()
