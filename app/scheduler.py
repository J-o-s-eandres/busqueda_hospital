from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app


def sync_job():
    with current_app.app_context():
        try:
            from .sync import sync_google_sheet

            result = sync_google_sheet()
            current_app.logger.info(
                f"Sync completed: {result['imported']} imported, "
                f"{result['duplicated']} duplicated, "
                f"{result['total']} total"
            )
        except Exception as e:
            current_app.logger.error(f"Sync failed: {e}")


def init_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=sync_job,
        trigger="interval",
        hours=1,
        id="sync_google_sheet",
        next_run_time=None,
    )
    scheduler.start()
