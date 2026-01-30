from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.setting import config
from app.core.models.shift import GlobalShiftSetting
from app.core.models.hr import EmployeeProfile, LoginCredential
from app.core.models.workwear import WorkwearConfig, WorkwearProfile
from app.core.models.training import TrainingProfile, SystemTrainingLevel
from app.core.models.parts_config import PartConfiguration
from app.core.models.production.production_plan import MonthlyProductionPlan
from app.core.models.production.hourly_production import HourlyProductionDocument
from app.core.models.fg_stock import FGStockDocument

from app.core.models.open_points import OpenPointProject, OpenPoint




motor_client = None

async def connect_to_mongo():
    global motor_client
    
    motor_client = AsyncIOMotorClient(str(config.MONGODB_URL))
    
    # Initialize Beanie with the database and the list of document models
    await init_beanie(
        database=motor_client[config.DATABASE_NAME], 
        document_models=[
            GlobalShiftSetting,
            EmployeeProfile, LoginCredential,
            WorkwearConfig, WorkwearProfile,
            TrainingProfile, SystemTrainingLevel,
            PartConfiguration,
            MonthlyProductionPlan,
            HourlyProductionDocument,
            FGStockDocument,

            OpenPointProject, OpenPoint,
            
        ]
    )
    print(f"Successfully connected to MongoDB at {config.DATABASE_NAME}")

async def close_mongo_connection():
    global motor_client
    if motor_client:
        motor_client.close()
        motor_client = None
    print("Closed MongoDB connection")

def get_database():
    """
    Get the database instance for raw collection access.
    Use this when you need to access collections not managed by Beanie.
    """
    if motor_client is None:
        raise Exception("Database client not initialized. Call connect_to_mongo() first.")
    return motor_client[config.DATABASE_NAME]