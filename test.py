from fastapi import FastAPI
import uvicorn
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from RabsProject.api.inventory import FgStock, StoreStock,  ToolManage, CustomerComplaint, ProductionPlan, RejectionDetail
from RabsProject.api.compliences import LoadWatch, Report, MultiStream, SingleStream, PPEViolation
from RabsProject.api.positioning import  BracketD, BracketE, PesCoverB, PesCoverA
from RabsProject.api.DOJO import Onboarding, HR_Induction, Level_1, Level_2, Level_3, Level_4, Workwear
from RabsProject.api.user import User_Camera
from RabsProject.api.inventory import StoreStockRegister
from RabsProject.services.scheduler import start_scheduler
from RabsProject.cores.auth.authorise import *
from RabsProject.api.Factory_Insp import GambaWalk



app = FastAPI()
os.makedirs("classification/uploads/BracketE", exist_ok=True)
app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")
app.mount("/Factory_Insp", StaticFiles(directory="/home/aiserver/Desktop/RABs/Factory_Insp"), name="Factory_Insp")
app.mount("/classification/uploads", StaticFiles(directory="classification/uploads"), name="uploads")
app.mount("/INVENTORY", StaticFiles(directory="/home/aiserver/Desktop/RABs/INVENTORY"), name="INVENTORY")
app.mount(
    "/INVENTORY/StoreStockRegister",
    StaticFiles(directory="/home/aiserver/Desktop/RABs/INVENTORY/StoreStockRegister"),
    name="store_stock_files"
)
app.mount("/detected_frames", StaticFiles(directory="/home/aiserver/Desktop/ffmpeg_stream/detected_frames"), name="detected_frames")

# Mount the base folder to a public route
app.mount("/DOJO", StaticFiles(directory="/home/aiserver/Desktop/RABs/DOJO"), name="DOJO")



MAX_BCRYPT_LEN = 72
origins = [
    "https://sharangaai.netlify.app",  # ✅ correct spelling
    "https://sharanga-ai.netlify.app",
    "http://localhost:5173",
    "https://rabs.alvision.in",
    "https://rabs.alvision.in/token",
    "https://sharangaai.netlify.app",
    "https://testing-sharangaai.netlify.app",
    "https://sharangaai-dojo.netlify.app"

]

app.add_middleware(
    CORSMiddleware,
    allow_origins= origins,  # List of domains allowed to access your API
    allow_credentials=True,  # Allows sending cookies, authorization headers
    allow_methods=["*"],     # Allows all HTTP methods: GET, POST, PUT, etc.
    allow_headers=["*", "Authorization", "Content-Type"]  )

now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
print(now_ist)

@app.get("/")
def read_root():
    return {"message": "Welcome to RabsProject"}

@app.on_event("startup")
def startup_event():
    start_scheduler()

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        # Truncate password to 72 bytes immediately
        password = form_data.password[:MAX_BCRYPT_LEN]

        user = authenticate_user(form_data.username, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token_expires = timedelta(hours=12)
        access_token = create_access_token(
            data={"sub": user.email, "role": user.role},
            expires_delta=access_token_expires  
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "message": f"Login successful for user {user.email}"
        }

    except Exception as e:
        raise RabsException(e, sys) from e

app.include_router(User_Camera.router)
app.include_router(MultiStream.router)
app.include_router(SingleStream.router)
app.include_router(LoadWatch.router)
app.include_router(PPEViolation.router)
app.include_router(Report.router)
app.include_router(BracketD.router)
app.include_router(BracketE.router)
app.include_router(PesCoverB.router)
app.include_router(PesCoverA.router)
app.include_router(FgStock.router)
app.include_router(StoreStock.router)
app.include_router(StoreStockRegister.router)
app.include_router(ToolManage.router)
app.include_router(CustomerComplaint.router)
app.include_router(ProductionPlan.router)
app.include_router(RejectionDetail.router)
app.include_router(Onboarding.router)
app.include_router(HR_Induction.router)
app.include_router(Level_1.router)
app.include_router(Level_2.router)
app.include_router(Level_3.router)
app.include_router(Level_4.router)
app.include_router(Workwear.router)
app.include_router(GambaWalk.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8015)



