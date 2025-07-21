from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from bot.utils import send_manifestation, send_card_prompt, send_card_reveal

tz = timezone("Asia/Kolkata")

def setup_jobs(app):
    scheduler = BackgroundScheduler(timezone=tz)

    # Morning Manifestation Burst
    scheduler.add_job(send_manifestation, 'cron', hour=9, minute=0, args=[app, 0], timezone=tz)
    scheduler.add_job(send_manifestation, 'cron', hour=9, minute=15, args=[app, 1], timezone=tz)
    scheduler.add_job(send_manifestation, 'cron', hour=9, minute=30, args=[app, 2], timezone=tz)

    # Card Draw (Face Down) at 10:00 IST
    scheduler.add_job(send_card_prompt, 'cron', hour=10, minute=0, args=[app], timezone=tz)

    # Card Reveal at 19:00 IST
    scheduler.add_job(send_card_reveal, 'cron', hour=19, minute=0, args=[app], timezone=tz)

    scheduler.start()
