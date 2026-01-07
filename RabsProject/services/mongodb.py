import logging
import yaml
import os, sys
from bson import ObjectId
from datetime import datetime, timedelta, date
from pymongo import MongoClient, errors
from RabsProject.services.send_email import EmailSender
from dateutil.relativedelta import relativedelta  
from bcrypt import hashpw, gensalt
from dotenv import load_dotenv
from passlib.context import CryptContext
from pymongo import MongoClient, ASCENDING, DESCENDING
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
from zoneinfo import ZoneInfo
email_sender = EmailSender()
load_dotenv()
ALLOWED_CATEGORIES = {"fire", "smoke", "ppe", "truck"}
ist = datetime.now(ZoneInfo("Asia/Kolkata"))



class MongoDBHandlerSaving:
    def __init__(self, url=os.getenv("MONGODB_URL_ACCESS"), db_name="RabsProject", 
                 user_collection_name="UserAuth", snapshot_collection_name='Snapshots',
                 sharanga_vision_collection_name='SharangaVision',
                 daily_Fg_stock_collection_name ='FGDailyStockSheet', 
                 monthly_Fg_stock_collection_name = 'FGMonthlyStockSheet',
                 monthly_store_stock_collection_name = 'StoreMonthlyStockSheet',
                 store_stock_collection_name = "StoreStockSheet",
                 store_stock_register_collection_name = "StoreStockRegister",
                 four_m_change_collection_name = "FourM-ChangeSheet",
                 tool_manage_collection_name = "ToolManageSheet",
                 customer_complaint_collection_name = "CustomerComplaintSheet",
                 production_plan_detail_collection_name="ProductionPlanDetail", 
                 monthly_production_plan_collection_name="MonthlyProductionPlan",
                 hourly_production_collection_name="HourlyProduction",
                 rejection_detail_collection_name="RejectionPlanDetail",
                 gemba_walk_collection_name="GembaWalkDetail",
                 master_types_collection_name="AccountMasterTypes",
                 account_collection_name="Account",
                 rfq_detail_collection_name="RFQ",
                 loading_unloading_collection_name="LoadingUnloading",
                 ppe_violation_collection_name="PPEViolations",
                 video_collection_name='Videos',
                 DOJO_collection_name="DOJO"):
        
        try:
            self.client = MongoClient(url)
            self.db = self.client[db_name]
            self.user_collection = self.db[user_collection_name]
            self.snapshot_collection = self.db[snapshot_collection_name]
            self.sharanga_vision_collection = self.db[sharanga_vision_collection_name]
            self.Daily_Fg_stock_collection = self.db[daily_Fg_stock_collection_name]
            self.monthly_fg_stock_config = self.db[monthly_Fg_stock_collection_name]
            self.monthly_store_stock_config = self.db[monthly_store_stock_collection_name]
            self.store_stock_collection = self.db[store_stock_collection_name]
            self.store_stock_register_collection = self.db[store_stock_register_collection_name]
            self.four_m_change_collection = self.db[four_m_change_collection_name]
            self.tool_manage_collection = self.db[tool_manage_collection_name]
            self.customer_complaint_collection = self.db[customer_complaint_collection_name]
            self.monthly_production_plan_collection = self.db[monthly_production_plan_collection_name]
            self.production_plan_detail_collection = self.db[production_plan_detail_collection_name]
            self.hourly_production_collection = self.db[hourly_production_collection_name]
            self.rejection_detail_collection = self.db[rejection_detail_collection_name]
            self.gemba_walk_collection = self.db[gemba_walk_collection_name]
            self.master_types_collection = self.db[master_types_collection_name]
            self.account_collection = self.db[account_collection_name]
            self.rfq_detail_collection = self.db[rfq_detail_collection_name]
            self.loading_unloading_collection = self.db[loading_unloading_collection_name]
            self.ppe_violation_collection = self.db[ppe_violation_collection_name]
            self.video_collection = self.db[video_collection_name]
            self.DOJO_collection = self.db[DOJO_collection_name] 
            logger.info("Connected to MongoDB successfully")

      
            # -------------------------
            # Indexes for Optimization
            # -------------------------

            # UserAuth
            self.user_collection.create_index("email", unique=True)

            # Snapshots & Videos
            self.snapshot_collection.create_index([("date", ASCENDING), ("camera_id", ASCENDING), ("category", ASCENDING)])
            self.video_collection.create_index([("date", ASCENDING), ("camera_id", ASCENDING), ("category", ASCENDING)])

            # FGDailyStock
            self.Daily_Fg_stock_collection.create_index("timestamp")
            self.Daily_Fg_stock_collection.create_index("item_description")

            # FGMonthlyStock
            self.monthly_fg_stock_config.create_index([("item_description", ASCENDING), ("month", ASCENDING)], unique=True)

            # StoreStock
            self.store_stock_collection.create_index("timestamp")
            self.store_stock_collection.create_index("item_description")

            # StoreMonthlyStock
            self.monthly_store_stock_config.create_index([("item_description", ASCENDING), ("month", ASCENDING)], unique=True)

            # Tool Manage
            self.tool_manage_collection.create_index("timestamp")

            # Customer Complaint
            self.customer_complaint_collection.create_index("timestamp")

            # Production Plan Detail
            self.production_plan_detail_collection.create_index("timestamp")
            self.monthly_production_plan_collection.create_index([("item_description", ASCENDING), ("month", ASCENDING)], unique=True)

            # Rejection Plan Detail
            self.rejection_detail_collection.create_index("timestamp")
            self.rejection_detail_collection.create_index("rm")

            # Gemba Walk Detail
            self.gemba_walk_collection.create_index("timestamp")

            # Account Master Types
            self.master_types_collection.create_index("type_name", unique=True)

            # Account
            self.account_collection.create_index("company_name")

            # RFQ Detail
            self.rfq_detail_collection.create_index("timestamp")

            # DOJO (Aadhaar-based uniqueness)
            self.DOJO_collection.create_index(
                "user_info.user_documents.id_proof.aadhaar",
                unique=True,
                sparse=True )
            

        except Exception as e:
            logger.exception("Error connecting to MongoDB")
            raise
        
    def close_connection(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

    @staticmethod
    def hash_password(password):
        return hashpw(password.encode(), gensalt()).decode()

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)



################################################################################################
             ########### User Management Method ###########
################################################################################################



    def save_user_to_mongodb(self, user_data, category, camera_info:None):
        try:
            existing_user = self.user_collection.find_one({"email": user_data["email"]})

            if existing_user:
                # Get existing cameras dictionary or create a new one
                cameras = existing_user.get("cameras", {})

                # Append to the category list, or create it if it doesn't exist
                if category not in cameras:
                    cameras[category] = []
                cameras[category].append(camera_info)

                filtered_user_data = {
                    "cameras": cameras
                }

            else:
                filtered_user_data = {
                    "name": user_data.get("name", "Unknown"),
                    "email": user_data["email"],
                    "password": self.hash_password(user_data.get("password", "defaultpassword")),
                    "role": user_data.get("role", "user"),
                    "cameras": {
                        category: [camera_info]
                    }
                }

            result = self.user_collection.update_one(
                {"email": user_data["email"]},
                {"$set": filtered_user_data},
                upsert=True
            )

            if result.upserted_id:
                logger.info(f"Created new user document for email: {user_data['email']}")
            else:
                logger.info(f"Updated existing user document for email: {user_data['email']}")

            return True

        except Exception as e:
            logger.exception("Error saving user to MongoDB")
            return False

    def get_user_data(self, email: str) -> dict:
        try:
            user = self.user_collection.find_one(
                {"email": email},
                {"password": 0}  # Exclude password from results
            )
            if user:
                user["_id"] = str(user["_id"])
                logger.info(f"Retrieved user data for email: {email}")
                return user
            
            logger.warning(f"No user found with email: {email}")
            return None

        except Exception as e:
            logger.exception(f"Error fetching user data for email: {email}")
            return None

    def delete_user(self, email: str) -> bool:
        try:
            # First verify user exists
            user = self.user_collection.find_one({"email": email})
            if not user:
                logger.warning(f"No user found with email: {email}")
                return False

            # Delete user document
            result = self.user_collection.delete_one({"email": email})
            
            if result.deleted_count > 0:
                logger.info(f"Successfully deleted user: {email}")
                return True
            
            logger.warning(f"Failed to delete user: {email}")
            return False

        except Exception as e:
            logger.exception(f"Error deleting user: {email}")
            return False

    def reset_password(self, email: str) -> bool:
        try:
            user = self.user_collection.find_one({"email": email})
            if not user:
                logger.warning(f"No user found with email: {email}")
                return False

            # Generate and hash temporary password
            temp_password = EmailSender.generate_temp_password()
            hashed_password = self.hash_password(temp_password)

            # Update password in database
            result = self.user_collection.update_one(
                {"email": email},
                {"$set": {
                    "password": hashed_password,
                    "force_password_change": True
                }}
            )

            if result.modified_count > 0:
                # Send email with temporary password using the new email configuration
                email_sender = EmailSender(receiver_email=email)
                if email_sender.send_password_reset_email(email, temp_password):
                    logger.info(f"Password reset successful and email sent for user: {email}")
                    return True
                else:
                    logger.error(f"Password reset successful but failed to send email for user: {email}")
                    return False

            logger.warning(f"Failed to reset password for user: {email}")
            return False

        except Exception as e:
            logger.exception(f"Error resetting password for user: {email}")
            return False

    def change_temp_password(self, email: str, temp_password: str, new_password: str) -> bool:
        """Change temporary password to new permanent password"""
        try:
            # First verify the temporary password
            # verify_result = self.verify_temp_password(email, temp_password)
            # if not verify_result["valid"]:
            if not self.verify_temp_password(email, temp_password):
                logger.warning(f"Invalid temporary password for user: {email}")
                return False

            # Hash and update with new password
            hashed_password = self.hash_password(new_password)
            result = self.user_collection.update_one(
                {"email": email},
                {
                    "$set": {
                        "password": hashed_password,
                        "force_password_change": False,
                        "password_last_changed": datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
                    }
                }
            )

            if result.modified_count > 0:
                # Send confirmation email
                email_sender = EmailSender(receiver_email=email)
                if email_sender.send_password_change_confirmation(email):
                    logger.info(f"Password changed successfully for user: {email}")
                    return True
                else:
                    logger.warning("Password changed but failed to send confirmation email")
                    return True  # Still return True as password was changed

            logger.warning(f"Failed to update password for user: {email}")
            return False

        except Exception as e:
            logger.exception(f"Error changing password for user: {email}")
            return False

    def verify_temp_password(self, email: str, temp_password: str) -> bool:
        try:
            user = self.user_collection.find_one({"email": email})
            if not user:
                return False

            stored_hashed_password = user.get("password", "")
            return self.verify_password(temp_password, stored_hashed_password)

        except Exception as e:
            logging.error(f"Error verifying temporary password for {email}: {str(e)}")
            return False




################################################################################################
             ########### Reporting and Fetching Methods for Camera RTSP ###########
################################################################################################



    def fetch_camera_rtsp_by_email_and_category(self, email, category):
        try:
            if category not in ALLOWED_CATEGORIES:
                raise ValueError(f"Invalid category '{category}'. Allowed: {ALLOWED_CATEGORIES}")

            logger.info(f"Fetching camera details for email: {email} and category: {category}")

            user_data = self.user_collection.find_one(
                {"email": email},
                {"_id": 0, "cameras": 1}
            )

            if user_data and "cameras" in user_data:
                cameras = user_data["cameras"]
                if category in cameras:
                    logger.info(f"Camera details found for email: {email}, category: {category}")
                    return cameras[category]
                else:
                    logger.warning(f"Category '{category}' not found in cameras for email: {email}")
                    return None
            else:
                logger.warning(f"No camera details found for email: {email}")
                return None

        except Exception as e:
            logger.exception("Error fetching camera details by email and category")
            return None

    def save_snapshot_to_mongodb(self, snapshot_path, date_time, camera_id, category):
        try:
            """Saves the snapshot path, date, time, and camera_id to MongoDB in the snapshot collection."""
            print("Saving snapshot...")
            date_folder = date_time.strftime('%Y-%m-%d')
            filename = os.path.basename(snapshot_path)
            
            document = {
                'date': date_folder,
                'category': category,
                'camera_id': camera_id,
                'images': [{
                    'filename': filename,
                    'path': snapshot_path,
                    'time': date_time.strftime('%H:%M:%S')
                }] }
            
            # Update the document if the date and camera_id already exist, otherwise insert a new one
            result = self.snapshot_collection.update_one(
                {'date': date_folder, 'category': category, 'camera_id': camera_id},
                {'$push': {'images': document['images'][0]}},
                upsert=True
            )
            
            if result.upserted_id:
                print(f"Created new document for date: {date_folder} and camera_id: {camera_id}")
            else:
                print(f"Updated existing document for date: {date_folder} and camera_id: {camera_id}")
            
            print(f"Saved snapshot and metadata to MongoDB: {document}")
            logging.info(f"Sending new snapshot document to mongodb for date: {date_folder} and camera_id: {camera_id}")

        except Exception as e:
            raise Exception(e, sys) from e

    def save_video_to_mongodb(self, video_path, date_time, camera_id, category):
        try:
            """Saves the video path, date, time, and camera_id to MongoDB in the video collection."""
            print("Saving video...")
            date_folder = date_time.strftime('%Y-%m-%d')
            filename = os.path.basename(video_path)
            
            document = {
                'date': date_folder,
                'category': category,
                'camera_id': camera_id,
                'videos': [{
                    'filename': filename,
                    'path': video_path,
                    'time': date_time.strftime('%H:%M:%S') }] }
            
            # Update the document if the date and camera_id already exist, otherwise insert a new one
            result = self.video_collection.update_one(
                {'date': date_folder, 'category': category, 'camera_id': camera_id},
                {'$push': {'videos': document['videos'][0]}},
                upsert=True  )
            
            if result.upserted_id:
                print(f"Created new snapshot document for date: {date_folder} and camera_id: {camera_id}")
            else:
                print(f"Updated existing document for date: {date_folder} and camera_id: {camera_id}")
            
            print(f"Saved video and metadata to MongoDB: {document}")
            logging.info(f"Sending new video document to mongodb for date: {date_folder} and camera_id: {camera_id}")

        except Exception as e:
            raise Exception(e, sys) from e

    def fetch_snapshots_by_time_range(self, year, month, day, start_time_str, end_time_str, camera_id, category):
        try:
            date_folder = datetime(year, month, day).strftime('%Y-%m-%d')
            result = self.snapshot_collection.find_one({'date': date_folder, 'camera_id': camera_id, "category":category})

            if not result or 'images' not in result:
                logging.info(f"No snapshots found for date {date_folder}, camera_id {camera_id}")
                return []

            # Parse start and end time
            start_time = datetime.strptime(start_time_str, '%H:%M')
            end_time = datetime.strptime(end_time_str, '%H:%M')

            filtered_images = []
            for image in result['images']:
                img_time = datetime.strptime(image['time'], '%H:%M:%S')
                if start_time.time() <= img_time.time() <= end_time.time():
                    filtered_images.append(image)

            logging.info(f"Fetched {len(filtered_images)} snapshot(s) between {start_time_str} and {end_time_str} on {date_folder}")
            return filtered_images

        except Exception as e:
            raise Exception(e, sys) from e

    def fetch_snapshots_by_date_and_camera(self, year, month, day, camera_id, category):
        """Fetch snapshots from MongoDB for a specific date and camera_id."""
        try:
            date_folder = datetime(year, month, day).strftime('%Y-%m-%d')
            result = self.snapshot_collection.find_one({'date': date_folder, 'camera_id': camera_id, "category" : category})
            logging.info(f"Fetch Snapshot from MongoDB for a specific date:{year}_{month}_{day} and camera_id:{camera_id}")
            return result['images'] if result else None
        except Exception as e:
            raise Exception(e, sys) from e

    def fetch_snapshots_by_month_and_camera(self, year, month, camera_id, category):
        """Fetch snapshots from MongoDB for a specific month and camera_id."""
        try:
            start_date = datetime(year, month, 1)
            # Calculate the end date of the month
            if month < 12:
                end_date = datetime(year, month + 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(year + 1, 1, 1) - timedelta(days=1)

            # Query for snapshots within the date range and specific camera_id
            results = self.snapshot_collection.find({
                'camera_id': camera_id,
                'category' : category,
                'date': {
                    '$gte': start_date.strftime('%Y-%m-%d'),
                    '$lte': end_date.strftime('%Y-%m-%d') }  })

            # Combine snapshots from all results
            snapshots = [image for result in results for image in result['images']]
            logging.info(f"Fetch Snapshot from MongoDB for a specific month:{year}_{month} and camera_id:{camera_id}")
            return snapshots if snapshots else None
        except Exception as e:
            raise Exception(e, sys) from e

    def fetch_all_cameras_by_date(self, year, month, day):
        """Fetch all camera_id and category data for a specific date."""
        try:
            date_folder = datetime(year, month, day).strftime('%Y-%m-%d')
            logger.info(f"Fetching all snapshot data for date: {date_folder}")

            # Query all documents for the specified date
            cursor = self.snapshot_collection.find({"date": date_folder})
            result = {}

            for doc in cursor:
                category = doc.get("category", "unknown")
                camera_id = doc.get("camera_id", "unknown")
                images = doc.get("images", [])

                if category not in result:
                    result[category] = {}

                result[category][camera_id] = images

            if result:
                logger.info(f"Found snapshot data for {len(result)} categories on {date_folder}")
            else:
                logger.warning(f"No snapshot data found for date: {date_folder}")

            return result

        except Exception as e:
            logger.exception("Error fetching all cameras by date")
            return None



###########################################################################################
                    ######### Fg Stock Monitoring Board #########
###########################################################################################



    def insert_daily_Fg_stock_entry(self, entry: dict):
        try:
            if "timestamp" not in entry or entry["timestamp"] is None:
                entry["timestamp"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
            result = self.Daily_Fg_stock_collection.insert_one(entry)
            logger.info(f"Inserted Fg stock entry with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.exception("Error inserting Fg stock entry")

    def get_Fg_stock_entries_by_day(self, query_date: date):
        try:
            start = datetime.combine(query_date, datetime.min.time())  # 00:00:00
            end = start + timedelta(days=1)                             # next day 00:00:00

            entries = list(self.Daily_Fg_stock_collection.find(
                {"timestamp": {"$gte": start, "$lt": end}}
            ))

            # Convert ObjectId to string for each document
            for entry in entries:
                entry["_id"] = str(entry["_id"])

            return entries
        except Exception as e:
            logger.exception("Error fetching entries by date")
            return []

    def update_daily_Fg_stock_entry(self, entry_id: str, updated_entry: dict):
        try:
            result = self.Daily_Fg_stock_collection.update_one(
                {"_id": ObjectId(entry_id)},
                {"$set": updated_entry}
            )
            if result.matched_count == 0:
                logger.warning(f"No stock entry found with ID: {entry_id}")
                return False
            logger.info(f"Updated stock entry with ID: {entry_id}")
            return True
        except Exception as e:
            logger.exception("Error updating stock entry")
            raise RuntimeError("Database update failed")
        
    def monthly_insert_Fg_stock_entry(self, config: dict):
        # Construct month string in "YYYY-MM" format
        config["month"] = f"{config['year']}-{config['month'].zfill(2)}"
        config["timestamp"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

        result = self.monthly_fg_stock_config.update_one(
            {"item_description": config["item_description"], "month": config["month"]},
            {"$set": config},
            upsert=True
        )

        return {
            "upserted_id": result.upserted_id,
            "matched_count": result.matched_count,
            "modified_count": result.modified_count
        }

    def get_Fg_stock_entries_by_month(self, item_description: str, month_str=None):
        return self.monthly_fg_stock_config.find_one({
            "item_description": item_description,
            "month": month_str
        })

    def get_yearly_fgstock_summary(self, item_description: str, year: int):
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)

        pipeline = [
            {"$match": {
                "item_description": item_description,
                "timestamp": {"$gte": start, "$lt": end}
            }},
            {"$addFields": {
                "month": {"$month": "$timestamp"}
            }},
            # Sort so latest entries per month come first
            {"$sort": {"month": 1, "timestamp": -1}},
            # Group and keep only the first (latest) document of each month
            {"$group": {
                "_id": "$month",
                "monthly_dispatched": {"$first": "$dispatched"},
                "schedule": {"$first": "$schedule"},
                "last_date": {"$first": "$timestamp"}
            }},
            {"$project": {
                "_id": 0,
                "month": "$_id",
                "monthly_dispatched": {"$ifNull": ["$monthly_dispatched", 0]},
                "schedule": 1,
                "last_date": 1
            }},
            {"$sort": {"month": 1}}
        ]

        return list(self.Daily_Fg_stock_collection.aggregate(pipeline))




###########################################################################################
                     ######### Store Stock Monitoring Board #########
###########################################################################################


    @property
    def store_stock_audit_collection(self):
        return self.db["store_stock_audit"]
    
    def get_store_stock_entry_by_id(self, entry_id: str):
        return self.store_stock_collection.find_one({"_id": ObjectId(entry_id)})

    def insert_store_stock_entry(self, entry: dict):
        try:
            if "timestamp" not in entry or entry["timestamp"] is None:
                entry["timestamp"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
            result = self.store_stock_collection.insert_one(entry)
            logger.info(f"Inserted stock entry with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.exception("Error inserting stock entry")

    def update_store_stock_entry(self, entry_id: str, update_data: dict):
        existing_entry = self.store_stock_collection.find_one({"_id": ObjectId(entry_id)})
        if not existing_entry:
            raise ValueError("Entry not found")

        # Increment the actual field if provided and not empty
        if "actual" in update_data:
            try:
                existing_actual = int(existing_entry.get("actual", 0))
                new_actual = int(update_data["actual"])
                update_data["actual"] = int(existing_actual + new_actual)
            except ValueError:
                raise ValueError("Invalid actual value (must be an integer)")

        # Perform the update
        result = self.store_stock_collection.update_one(
            {"_id": ObjectId(entry_id)},
            {"$set": update_data}
        )

    def monthly_insert_store_stock_entry(self, config: dict):
        # Construct month string in "YYYY-MM" format
        config["month"] = f"{config['year']}-{config['month'].zfill(2)}"
        config["timestamp"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

        result = self.monthly_store_stock_config.update_one(
            {"item_description": config["item_description"], "month": config["month"]},
            {"$set": config},
            upsert=True
        )

        return {
            "upserted_id": result.upserted_id,
            "matched_count": result.matched_count,
            "modified_count": result.modified_count
        }

    def get_store_stock_entries_by_month(self, item_description: str, month_str=None):
        return self.monthly_store_stock_config.find_one({
            "item_description": item_description,
            "month": month_str
        })

    def get_store_stock_entries_by_day(self, year: int, month: int, day: int):
        try:
            # Get the start and end datetime for the day
            start = datetime(year, month, day)
            end = start + timedelta(days=1)

            entries = list(self.store_stock_collection.find(
                {"timestamp": {"$gte": start, "$lt": end}}
            ))

            # Convert ObjectId to string for frontend
            for entry in entries:
                entry["_id"] = str(entry["_id"])

            return entries
        except Exception as e:
            logger.exception("Error fetching daily store stock entries")
            return []

    def get_latest_store_stock_entry(self, item_description: str, year: int, month: int):
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)

        return self.store_stock_collection.find_one(
            {
                "item_description": item_description,
                "timestamp": {"$gte": start, "$lt": end}
            },
            sort=[("timestamp", DESCENDING)]
        )



###########################################################################################
                         ######### Tool Management Board #########
###########################################################################################



    def insert_tool_management_entry(self, entry: dict):
        try:
            if "timestamp" not in entry or entry["timestamp"] is None:
                entry["timestamp"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
            result = self.tool_manage_collection.insert_one(entry)
            logger.info(f"Inserted tool management entry with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.exception("Error inserting tool management entry")

    def get_tool_management_entry_by_month(self, year, month):
        start_date = datetime(year, month, 1)
        end_date = start_date + relativedelta(months=1)
        
        entries = self.tool_manage_collection.find({
            "timestamp": {"$gte": start_date, "$lt": end_date}
        })

        result = []
        for entry in entries:
            entry["id"] = str(entry["_id"])  # convert ObjectId to string
            del entry["_id"]  # optional: remove raw ObjectId if not needed
            result.append(entry)

        return result

    def update_tool_management_entry(self, entry_id: str, updated_fields: dict):
        try:
            result = self.tool_manage_collection.update_one(
                {"_id": ObjectId(entry_id)},
                {"$set": updated_fields}
            )
            if result.matched_count == 0:
                raise ValueError("No tool management entry found with the given ID.")
            logger.info(f"Updated tool management entry with ID: {entry_id}")
            return True
        except Exception as e:
            logger.exception("Error updating tool management entry")
            raise



###########################################################################################
                ######### customer compaint  Board #########
###########################################################################################



    def insert_customer_complaint_entry(self, entry: dict):
        try:
            if "timestamp" not in entry or entry["timestamp"] is None:
                entry["timestamp"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
            result = self.customer_complaint_collection.insert_one(entry)
            logger.info(f"Inserted customer complaint entry with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.exception("Error inserting customer complaint entry")

    def get_customer_complaint_entry_by_quarter(self, year: int, quarter: int):
        if quarter not in [1, 2, 3, 4]:
            raise ValueError("Quarter must be 1, 2, 3, or 4.")

        # Calculate start and end date of the quarter
        start_month = 3 * (quarter - 1) + 1
        start_date = datetime(year, start_month, 1)
        end_date = start_date + relativedelta(months=3)

        # Query Mongo directly (timestamp is stored as datetime)
        query = {"timestamp": {"$gte": start_date, "$lt": end_date}}
        entries = self.customer_complaint_collection.find(query)

        result = []
        for entry in entries:
            entry["id"] = str(entry["_id"])
            del entry["_id"]
            result.append(entry)

        return result

    def update_customer_complaint_entry(self, entry_id: str, updated_fields: dict):
        try:
            result = self.customer_complaint_collection.update_one(
                {"_id": ObjectId(entry_id)},
                {"$set": updated_fields}
            )
            if result.matched_count == 0:
                raise ValueError("No customer complaint entry found with the given ID.")
            logger.info(f"Updated customer complaint entry with ID: {entry_id}")
            return True
        except Exception as e:
            logger.exception("Error updating customer complaint entry")
            raise



###########################################################################################
                ######### Production Plan detail Board #########
###########################################################################################



    def save_production_plan_detail(self, entry: dict):
        try:
            entry["timestamp"] = entry.get("timestamp") or datetime.now()
            result = self.production_plan_detail_collection.insert_one(entry)
            logger.info("Production plan detail saved successfully", extra={"entry_id": str(result.inserted_id)})
            return str(result.inserted_id)
        except Exception as e:
            logger.exception("Failed to save production plan detail")
            raise

    def update_production_plan_detail(self, entry_id: str, updated_fields: dict):
        try:
            result = self.production_plan_detail_collection.update_one(
                {"_id": ObjectId(entry_id)},
                {"$set": updated_fields}
            )
            if result.matched_count == 0:
                raise ValueError("No production plan detail found with the given ID.")
            logger.info(f"Updated production plan detail with ID: {entry_id}")
            return True
        except Exception as e:
            logger.exception("Error updating production plan detail")
            raise

    def get_production_plan_details_by_month(self, year, month):
        start_date = datetime(year, month, 1)
        end_date = start_date + relativedelta(months=1)

        entries = self.production_plan_detail_collection.find({
            "timestamp": {"$gte": start_date, "$lt": end_date}})

        result = []
        for entry in entries:
            entry["id"] = str(entry["_id"])  # convert ObjectId to string
            del entry["_id"]  # optional: remove raw ObjectId if not needed
            result.append(entry)

        return result
       
    def monthly_insert_production_plan_entry(self, config: dict):
        # Construct month string in "YYYY-MM" format
        config["month"] = f"{config['year']}-{config['month'].zfill(2)}"
        config["timestamp"] = datetime.utcnow()

        result = self.monthly_production_plan_collection.update_one(
            {"item_description": config["item_description"], "month": config["month"]},
            {"$set": config},
            upsert=True
        )

        return {
            "upserted_id": result.upserted_id,
            "matched_count": result.matched_count,
            "modified_count": result.modified_count
        }

    def get_production_plan_entries_by_month(self, item_description: str, month_str=None):
        return self.monthly_production_plan_collection.find_one({
            "item_description": item_description,
            "month": month_str
        })


    
###########################################################################################
                ######### Rejection Plan detail Board #########
###########################################################################################



    def save_rejection_detail(self, entry: dict):
        try:
            entry["timestamp"] = entry.get("timestamp") or datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
            result = self.rejection_detail_collection.insert_one(entry)
            logger.info("Rejection plan detail saved successfully", extra={"entry_id": str(result.inserted_id)})
            return str(result.inserted_id)
        except Exception as e:
            logger.exception("Failed to save rejection plan detail")
            raise

    def update_rejection_detail(self, entry_id: str, updated_fields: dict):
        try:
            result = self.rejection_detail_collection.update_one(
                {"_id": ObjectId(entry_id)},
                {"$set": updated_fields}
            )
            if result.matched_count == 0:
                raise ValueError("No rejection plan detail found with the given ID.")
            logger.info(f"Updated rejection plan detail with ID: {entry_id}")
            return True
        except Exception as e:
            logger.exception("Error updating rejection plan detail")
            raise

    def get_rejection_details_data_by_month(self, year, month):
        start_date = datetime(year, month, 1)
        end_date = start_date + relativedelta(months=1)

        entries = self.rejection_detail_collection.find({
            "timestamp": {"$gte": start_date, "$lt": end_date}})

        result = []
        for entry in entries:
            entry["id"] = str(entry["_id"])  # convert ObjectId to string
            del entry["_id"]  # optional: remove raw ObjectId if not needed
            result.append(entry)

        return result
    
    def get_rejection_details_by_month_and_item(self, year: int, month: int, rm: str):
        start_date = datetime(year, month, 1)
        end_date = start_date + relativedelta(months=1)

        entries = self.rejection_detail_collection.find({
            "timestamp": {"$gte": start_date, "$lt": end_date},
            "rm": rm   # <-- changed here
        })

        result = []
        for entry in entries:
            entry["id"] = str(entry["_id"])
            entry.pop("_id", None)
            result.append(entry)

        return result



############################################################################################
                   #########         DOJO 2.0 Initialisation        ###########
############################################################################################



    def save_onboarding_info(self, user_id: str, user_info: dict, user_documents: dict):
        try:
            # Embed user_documents inside user_info
            user_info["user_documents"] = user_documents

            onboarding_data = {
                "user_id": user_id,
                "user_info": user_info,
                "updated_at": datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
            }

            # Add created_at if new document
            existing = self.DOJO_collection.find_one({"user_id": user_id})
            if not existing:
                onboarding_data["created_at"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

            # Save to DB (upsert)
            self.DOJO_collection.update_one(
                {"user_id": user_id},
                {"$set": onboarding_data},
                upsert=True
            )

            print(f"Onboarding info saved for user_id: {user_id}")

        except Exception as e:
            print(f"Error saving onboarding info: {e}")

    def save_hr_induction_info(self, user_id: str, user_info: dict):
        try:
            onboarding_data = {
                "user_id": user_id,
                "user_info": user_info,
                "updated_at": datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
            }

            # Add created_at if new document
            existing = self.DOJO_collection.find_one({"user_id": user_id})
            if not existing:
                onboarding_data["created_at"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

            # Save to DB (upsert)
            self.DOJO_collection.update_one(
                {"user_id": user_id},
                {"$set": onboarding_data},
                upsert=True
            )

            print(f"Onboarding info saved for user_id: {user_id}")

        except Exception as e:
            print(f"Error saving onboarding info: {e}")


