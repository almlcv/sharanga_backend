from pydantic import BaseModel
import re
from pydantic import BaseModel, field_validator, model_validator, root_validator
from pydantic import BaseModel, validator
from datetime import datetime, date, timezone
from pydantic import BaseModel, Field, EmailStr,field_validator,ValidationInfo
from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import List, Dict, Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel, field_validator, model_validator, root_validator
from pydantic import BaseModel, validator
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from typing import Union
from typing import List, Dict, Optional
from pydantic_core import PydanticCustomError
from enum import Enum


    
class YearMonthValidator(BaseModel):
    year: int = Field(..., ge=2000, le=2100, description="Year in YYYY format")
    month: int = Field(..., ge=1, le=12, description="Month between 1 and 12")

    @field_validator("year")
    def validate_year(cls, v: int) -> int:
        if v < 2000 or v > 2100:
            raise ValueError("Year must be between 2000 and 2100.")
        if len(str(v)) != 4:
            raise ValueError("Year must be in YYYY format (e.g., 2025).")
        return v

class DateValidator(BaseModel):
    year: int = Field(..., ge=2000, le=2100, description="Year in YYYY format")
    month: int = Field(..., ge=1, le=12, description="Month between 1 and 12")
    day: int = Field(..., ge=1, le=31, description="Day of the month")

    @field_validator("year")
    def validate_year(cls, v: int) -> int:
        if v < 2000 or v > 2100:
            raise ValueError("Year must be between 2000 and 2100.")
        if len(str(v)) != 4:
            raise ValueError("Year must be in YYYY format (e.g., 2025).")
        return v

    @field_validator("day")
    def validate_day(cls, v: int, values) -> int:
        year = values.get("year")
        month = values.get("month")

        if year and month:
            try:
                datetime(year, month, v)  # Will raise ValueError if invalid
            except ValueError:
                raise ValueError(f"Invalid day {v} for {year}-{month}.")
        return v




class Token(BaseModel):
    access_token: str
    token_type: str
    message: str 

class TokenData(BaseModel):
    email: Optional[str] = None

class ModelInput(BaseModel):
    model: str

class CameraInput(BaseModel):
    camera_id: str
    rtsp_link: str
    category: Optional[str] = None
    # polygon_points: Optional[str] = None 

class User(BaseModel):
    name: str
    email: str
    password: str
    category: Optional[str] = None
    role: str
    cameras: Dict[str, List[CameraInput]]
    disabled: Optional[bool] = None

class UserInput(BaseModel):
    name: str
    email: str
    password: str
    role: str

class SnapDate(BaseModel):
    filename: str
    path: str
    time: str

class SnapMonth(BaseModel):
    filename: str
    path: str
    time: str

class SnapshotCountResponse(BaseModel):
    count: int
    snapshots: List[SnapDate]  # Replace SnapDate with your snapshot model

class SnapshotImage(BaseModel):
    filename: str
    path: str
    time: str

class SnapshotGroup(BaseModel):
    camera_id: str
    images: List[SnapshotImage]

class SnapshotCategoryData(BaseModel):
    category: str
    cameras: List[SnapshotGroup]

class SnapshotMultiResponse(BaseModel):
    date: str
    total_images: int
    data: List[SnapshotCategoryData]


class BinsAvailable(BaseModel):
    rabs_bins: Optional[int]
    ijl_bins: Optional[int]


class IJLBinsUpdateRequest(BaseModel):
    part_name: str
    bins_quantity: int 
    day:  int = Field(..., ge=0, le=31, description="Date between 1 and 31")
    month: int = Field(..., ge=1, le=12, description="Month between 1 and 12")
    year: int = Field(..., ge=2000, le=2100, description="Year in YYYY format")

class DailyFgStockEntrySheet(BaseModel):
    item_description: str
    item_code: str
    minimum: int
    todays_planning: str
    current: int  # ✅ Changed from str to int
    dispatched: Optional[int]
    balance: Optional[int]
    bins_available : BinsAvailable = BinsAvailable(rabs_bins=0, ijl_bins=0)
    next_action: str
    resp_person: str
    timestamp: Optional[datetime]
  

class AddBinsRequest(BaseModel):
    part_name: str                # Example: "ALTROZ BRACKET-D"
    year: int
    month: int
    day: int
    rabs_bins: Optional[int] = 0  # total bins to add in RABS
    ijl_bins: Optional[int] = 0   # total bins to add in IJL


class MonthlyFgStockEntrySheet(BaseModel):
    year: str
    month: str
    item_description: str
    schedule: int
    maximum: int




class LocationPriority(BaseModel):
    p1: Optional[str] = Field(default=None, description="Primary location")
    p2: Optional[str] = Field(default=None, description="Secondary location")
    p3: Optional[str] = Field(default=None, description="Tertiary location")

    def capitalize_locations(self):
        for attr in ["p1", "p2", "p3"]:
            val = getattr(self, attr)
            if val and len(val) > 0:
                # Only change the first character to uppercase
                setattr(self, attr, val[0].upper() + val[1:])
        return self
    

class MonthlyStoreStockEntrySheet(BaseModel):
    month: str
    year: str
    item_description: str
    schedule: int
    

class Base64File(BaseModel):
    filename: str
    content: Optional[str] = ""  # can be empty


class StoreStockMonitoringSheet(BaseModel):
    item_description: str
    minimum: int
    maximum: int
    current: Optional[float] = 0.0
    resp_person: str
    location: LocationPriority
    status: str
    actual: Optional[Union[int, str]] = None
    timestamp: datetime = None
    # updated_at: Optional[datetime] = None 

    @validator("actual", pre=True)
    def parse_int_fields(cls, v):
        if v == "" or v is None:
            return 0
        return int(v)


    @root_validator(pre=True)
    def calculate_current_from_location(cls, values):
        """Auto-calculate `current` as sum of numbers in p1+p2+p3 (supports decimals)"""
        import re
        location = values.get("location")
        if location:
            total = 0
            for key in ["p1", "p2", "p3"]:
                val = getattr(location, key, None)
                if val:
                    # Match both integers and floats
                    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(val))]
                    total += sum(nums)
            values["current"] = total # if you want to keep it as int
        return values





class StoreStockItem(BaseModel):
    item_description: str
    received_qty: Optional[int] = None
    QC: str = None
    location: str = None
    lot_no: Optional[str] = None
    TC: List[Base64File]   # Transport Charges per item
    remark: Optional[str] = None

    # ✅ Make the entire location string uppercase automatically
    @validator("location", pre=True, always=True)
    def uppercase_location(cls, v):
        if v:
            return v.strip().upper()
        return v
    

class StoreStockEntry(BaseModel):
    Invoice: List[Base64File]  # Single Invoice for all items in this truck
    items: List[StoreStockItem] 



# class StoreStockExit(BaseModel):
#     item_description: str
#     issued_qty: Optional[int] = None
#     location: Optional[str] = None
#     remark:Optional[str] = None
#     timestamp: datetime = None  # Optional on input, added automatically

class StoreStockExit(BaseModel):
    item_description: str
    part_name:str
    machine_no:str
    issued_qty: int
    location: str 
    approval_photo: List[Base64File]
    remark:Optional[str] = None
    timestamp: datetime = None  # Optional on input, added automatically

    # ✅ Make the entire location string uppercase automatically
    @validator("location", pre=True, always=True)
    def uppercase_location(cls, v):
        if v:
            return v.strip().upper()
        return v




class FourMChangeSheet(BaseModel):
    man:str
    machine:str
    method:str
    material:str
    resp_person: str
    timestamp:datetime = None


class ToolManageSheet(BaseModel):
    machine: str
    mould_name: str
    plan_pm_date: str
    actual_pm_date: str
    month_end_CUM: str
    status: str
    remarks: Optional[str] = None
    resp_person: str
    timestamp: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @model_validator(mode="after")
    def check_remarks(cls, values):
        plan_date = values.plan_pm_date
        actual_date = values.actual_pm_date
        remarks = values.remarks

        if plan_date and actual_date and plan_date != actual_date:
            if not remarks or remarks.strip() == "":
                raise ValueError("Remarks are mandatory if plan_pm_date and actual_pm_date are different")
        return values


# class CustomerComplaintSheet(BaseModel):
#     customer : str
#     part_name:str
#     complaint:str
#     complaint_date:str
#     part_received_date:str
#     problem_description:str
#     quantity: int
#     line_name : str
#     tracebility : str
#     first_repeat: str
#     supplier: str
#     process: str
#     temporary_action: str
#     temporary_target_date: str
#     root_cause: str
#     permanent_action: str
#     permanent_target_date: str
#     responsibility: str
#     status: str
#     standerdization: str
#     horizental_deployment: str
#     resp_person: str
#     timestamp: datetime = None  # Optional on input, added automatically




class CustomerComplaintSheet(BaseModel):
    customer : str
    part_name:str
    complaint:str
    complaint_date:Optional[Union[str, date]] = None
    part_received_date:Optional[Union[str, date]] = None
    problem_description:str
    quantity: int
    line_name : str
    tracebility : Optional[Union[str, date]] = None
    first_repeat: str
    supplier: str
    process: str
    temporary_action: str
    temporary_target_date: Optional[Union[str, date]] = None
    root_cause: str
    permanent_action: str
    permanent_target_date:Optional[Union[str, date]] = None
    responsibility: str
    status: str
    standerdization: str
    horizental_deployment: str
    resp_person: str
    timestamp: datetime = None  # Optional on input, added automatically



class CustomerComplaintUpdate(BaseModel):
    customer: Optional[str] = None
    part_name: Optional[str] = None
    complaint: Optional[str] = None
    complaint_date: Optional[Union[str, date]] = None
    part_received_date: Optional[Union[str, date]] = None
    problem_description: Optional[str] = None
    quantity: Optional[int] = None
    line_name: Optional[str] = None
    tracebility: Optional[Union[str, date]] = None
    first_repeat: Optional[str] = None
    supplier: Optional[str] = None
    process: Optional[str] = None
    temporary_action: Optional[str] = None
    temporary_target_date: Optional[Union[str, date]] = None
    root_cause: Optional[str] = None
    permanent_action: Optional[str] = None
    permanent_target_date: Optional[Union[str, date]] = None
    responsibility: Optional[str] = None
    resp_person: Optional[str] = None
    status: Optional[str] = None
    standerdization: Optional[str] = None
    horizental_deployment: Optional[str] = None
    timestamp: Optional[datetime] = None




class Bracket_D_UploadResponse(BaseModel):
    file_id: str

class PasswordChangeRequest(BaseModel):
    email: str
    temp_password: str
    new_password: str

# class ProductionPlanDetail(BaseModel):
#     part_description: str
#     # machine:str
#     schedule: str
#     plan: str
#     actual: str
#     resp_person: str
#     timestamp: datetime = None  # Optional on input, added automatically



class ProductionPlanDetail(BaseModel):
    part_description: str
    plan: int
    actual_RH: int
    actual_LH: int
    resp_person: str
    timestamp: datetime = None  # Optional on input, added automatically

class MonthlyProductionPlan(BaseModel):
    year: str 
    month: str 
    item_description: str
    schedule: int
    dispatch_quantity_per_day:int
    day_stock_to_kept: int
    resp_person: str
    timestamp: datetime = None  # Optional on input, added automatically


class RejectionDetailSheet(BaseModel):
    part_description: str
    rm: str
    ok_parts: float
    rejections: float
    lumps: float
    runner: float
    isssued: float
    # machine: str
    resp_person: str
    timestamp: datetime = None  # Optional on input, added automatically




##################################################################################
########################### Factory Inspection #############################################
##################################################################################


class Base64File(BaseModel):
    filename: str
    content: Optional[str] = ""  # can be empty

class GembaDoc(BaseModel):
    before_photo: Optional[List[Base64File]] = []  # photos taken at submission (before)
    after_photo: Optional[List[Base64File]] = []   # photos taken when status changes (after)
    after_observation: Optional[str] = None

class GembaInfo(BaseModel):
    area: Optional[str] = None
    observation: Optional[str] = None
    # five_whys: Optional[List[str]] = Field(default_factory=list, max_items=5)
    action_required: Optional[str] = None
    assign_to: Optional[str] = None
    target_date: Optional[Union[str, date]] = None
    status: Optional[str] = None
    

# ✅ Wrap payload + docs in a single request model
class GembaWalkCategories(BaseModel):
    payload: GembaInfo
    docs: GembaDoc




##################################################################################
########################### DOJO 2.0 #############################################
##################################################################################


########################### Onboarding Candidate #################################

class Base64File(BaseModel):
    filename: str
    content: Optional[str] = ""  # can be empty


# class OnboardingUserDoc(BaseModel):
#     avatar: Optional[List[Base64File]] = []
#     id_proof: Optional[Dict[str, List[Base64File]]] = {}
#     education_certificates: Optional[Dict[str, List[Base64File]]] = {}
#     experience_letters: Optional[List[Base64File]] = []
#     other_documents: Optional[Dict[str, List[Base64File]]] = {}

class OnboardingUserDoc(BaseModel):
    avatar: Optional[Base64File] = None  # single image
    id_proof: Optional[List[Base64File]] = []  # multiple images
    education_certificates: Optional[List[Base64File]] = []
    experience_letters: Optional[List[Base64File]] = []
    other_documents: Optional[List[Base64File]] = []


class OnboardingUserInfo(BaseModel):
    full_name: str
    dob: str
    phone: str = Field(
        ...,
        pattern=r"^[6-9]\d{9}$",
        description="Valid 10-digit Indian phone number"
    )
    aadhaar_number: str = Field(
        ...,
        pattern=r"^\d{12}$",
        description="Valid 12-digit aadhaar number"
    )

     
    employees_role: str
    email: Optional[EmailStr] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    qualification: Optional[str] = None
    experience: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    emergency_contact_number: Optional[str] = None
    salary_account_number: Optional[str] = None
    blood_group: Optional[str] = None
    marital_status: Optional[str] = None

    # ✅ Pydantic v2 uses `@field_validator` instead of `@validator`
    @field_validator("phone")
    def validate_phone(cls, v):
        if not re.fullmatch(r"^[6-9]\d{9}$", v):
            raise ValueError("Phone must be a valid 10-digit Indian mobile number starting with 6-9")
        return v

    @field_validator("aadhaar_number")
    def validate_aadhaar_number(cls, v):
        if not re.fullmatch(r"^\d{12}$", v):
            raise ValueError("aadhaar number must be exactly 12 digits")
        return v


# ✅ Wrap payload + docs in a single request model
class OnboardingRequest(BaseModel):
    payload: OnboardingUserInfo
    docs: OnboardingUserDoc



########################## HR INduction #########################################

class InductionVideo(BaseModel):
    title: str
    link: HttpUrl
    status: Optional[str] = "Not Watched"
    watched_at: Optional[datetime] = None

class InductionInfo(BaseModel):
    videos: List[InductionVideo]
    form_uploaded: bool = False
    form_link: Optional[HttpUrl] = None
    completed: bool = False
    completed_at: Optional[datetime] = None

class UploadFormSchema(BaseModel):
    user_id: str
    form_link: HttpUrl

class MarkVideoWatchedSchema(BaseModel):
    user_id: str
    video_title: str

class MarkOJTCompletedSchema(BaseModel):
    user_id: str
    title: str

class StarType(str, Enum):
    silver = "silver"   # only option
