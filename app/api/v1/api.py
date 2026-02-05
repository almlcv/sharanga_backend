from fastapi import APIRouter

from app.api.routes import (hr, employee, password_reset, training, workwear, shifts, auth, 
                            parts_config, open_points, fg_stock, production_report)
from app.api.routes.production import hourly_production, production_plan

api_router = APIRouter()



api_router.include_router(auth.router)
api_router.include_router(password_reset.router)
api_router.include_router(shifts.router)
api_router.include_router(hr.router)
api_router.include_router(password_reset.hr_router)
api_router.include_router(employee.router)
api_router.include_router(password_reset.employee_router)
api_router.include_router(training.router)
api_router.include_router(workwear.router)
api_router.include_router(parts_config.router)
api_router.include_router(production_plan.router)
api_router.include_router(hourly_production.router)
api_router.include_router(fg_stock.router)
api_router.include_router(production_report.router)

api_router.include_router(open_points.router)



