from fastapi import HTTPException
from app.core.models.workwear import WorkwearConfig, ConfigItem
from app.core.schemas.workwear import CreateWorkwearConfigSchema, UpdateWorkwearConfigSchema

class WorkwearConfigService:

    @staticmethod
    async def create_config(schema: CreateWorkwearConfigSchema) -> WorkwearConfig:
        # Check if config name exists
        existing = await WorkwearConfig.find_one(WorkwearConfig.config_name == schema.config_name)
        if existing:
            raise HTTPException(status_code=400, detail="Config name already exists")

        new_config = WorkwearConfig(**schema.model_dump())
        await new_config.insert()
        return new_config

    @staticmethod
    async def get_all_configs():
        return await WorkwearConfig.find_all().to_list()

    @staticmethod
    async def update_config(config_name: str, schema: UpdateWorkwearConfigSchema):
        config = await WorkwearConfig.find_one(WorkwearConfig.config_name == config_name)
        if not config:
            raise HTTPException(status_code=404, detail="Config not found")

        # Update fields if provided
        if schema.display_name is not None:
            config.display_name = schema.display_name
        if schema.items is not None:
            config.items = schema.items
        
        await config.save()
        return config

    @staticmethod
    async def delete_config(config_name: str):
        config = await WorkwearConfig.find_one(WorkwearConfig.config_name == config_name)
        if not config:
            raise HTTPException(status_code=404, detail="Config not found")
        
        await config.delete()
        return {"message": f"Config '{config_name}' deleted"}