from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from RabsProject.services.mongodb import MongoDBHandlerSaving

mongo_handler = MongoDBHandlerSaving()

def create_sunday_entries():
    ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    
    if ist.weekday() == 6:  # Sunday (Mon=0, Sun=6)
        yesterday = ist - timedelta(days=1)
        saturday_entries = list(mongo_handler.Daily_Fg_stock_collection.find({
            "year": yesterday.year,
            "month": yesterday.month,
            "day": yesterday.day
        }))

        if not saturday_entries:
            print("⚠️ Saturday entries not found, skipping Sunday auto-fill")
            return

        for entry in saturday_entries:
            entry_copy = entry.copy()
            entry_copy.pop("_id", None)  # reset ObjectId
            entry_copy.update({
                "year": ist.year,
                "month": ist.month,
                "day": ist.day,
                "timestamp": ist,
            })
            mongo_handler.insert_daily_Fg_stock_entry(entry_copy)

        print("✅ Sunday entries auto-created at midnight")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(create_sunday_entries, "cron", hour=0, minute=0)  # run daily at 12:00 AM
    scheduler.start()
