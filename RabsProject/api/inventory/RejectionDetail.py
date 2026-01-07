from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime, timezone
from bson import ObjectId
from RabsProject.pymodels.models import *
from zoneinfo import ZoneInfo
from RabsProject.config.RejectionConfig import DEFAULT_MONTHLY_REJECTION_DETAIL_ENTRIES
from RabsProject.services.mongodb import MongoDBHandlerSaving
from RabsProject.pymodels.models import RejectionDetailSheet, User
from RabsProject.cores.auth.authorise import get_current_user, admin_required, production_required



router = APIRouter(tags=["Rejection Detail"])
mongo_handler = MongoDBHandlerSaving()
ist = datetime.now()


def convert_object_ids(data):
    """Recursively convert all ObjectId instances in the data to str."""
    if isinstance(data, dict):
        return {
            k: convert_object_ids(str(v) if isinstance(v, ObjectId) else v)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [convert_object_ids(item) for item in data]
    return data

#######################################  DAILY REJECTION SHEET ###########################################

@router.post("/save_rejection_detail", response_model=dict)
def save_rejection_detail(day: int, entry: RejectionDetailSheet, current_user: User = Depends(production_required)):
    try:
        entry_dict = entry.dict()
        day, month, year = day, ist.month, ist.year
        entry_dict["timestamp"] =  datetime(year, month, day, tzinfo=timezone.utc)
        inserted_id = mongo_handler.save_rejection_detail(entry_dict)
        return {"message": "Rejection detail saved successfully", "entry_id": str(inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update_rejection_detail/{entry_id}", response_model=dict)
def update_rejection_detail(entry_id: str, updated_fields: RejectionDetailSheet = Body(...), current_user: User = Depends(production_required)):
    try:
        update_dict = updated_fields.dict(exclude_unset=True)
        # day, month, year = ist.day, ist.month, ist.year
        # update_dict["timestamp"] =  datetime(year, month, day, tzinfo=timezone.utc)
        mongo_handler.update_rejection_detail(entry_id, update_dict)
        return {"message": "Rejection detail updated successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


#######################################  MONTHLY REJECTION SHEET ###########################################


@router.get("/get_rejection_details_by_month", response_model=dict)
def get_rejection_details_by_month(params: YearMonthValidator = Depends(), current_user: User = Depends(production_required)):
    try:
        month, year = params.month, params.year
        entries = mongo_handler.get_rejection_details_data_by_month(year, month)

        if entries:
            formatted_records = []
            for e in entries:
                e_copy = {}
                for k, v in e.items():
                    if k == "_id":
                        e_copy["id"] = str(v)  # Rename _id to id
                    else:
                        e_copy[k] = v
                # Add scrap_sum
                scrap_sum = float(e.get("rejections", 0) or 0) + float(e.get("lumps", 0) or 0) + float(e.get("runner", 0) or 0)
                e_copy["scrap_sum"] = scrap_sum
                formatted_records.append(e_copy)

            return {
                "message": "Entries fetched from MongoDB",
                "year": year,
                "month": month,
                "records": formatted_records}

        else:
            inserted_entries = []
            for entry in DEFAULT_MONTHLY_REJECTION_DETAIL_ENTRIES:
                entry_copy = entry.copy()
                day, month, year = ist.day, ist.month, ist.year
                entry_copy["timestamp"] =  datetime(year, month, day, tzinfo=timezone.utc)
                inserted_id = mongo_handler.save_rejection_detail(entry_copy)
                entry_copy["_id"] = str(inserted_id)
                inserted_entries.append(entry_copy)
            return {
                "message": "Default entries created",
                "year": year,
                "month": month,
                "records": inserted_entries}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


####################################### NEW MONTHLY SUMMERY SHEET ###########################################


@router.get("/get_rejection_details_by_part_description", response_model=dict)
def get_rejection_details_by_part_description(params: YearMonthValidator = Depends(), current_user: User = Depends(production_required)):
    try:
        month, year = params.month, params.year
        # Step 1: Extract unique RM values
        unique_rms = list({entry["rm"] for entry in DEFAULT_MONTHLY_REJECTION_DETAIL_ENTRIES})

        rm_wise_results = []

        for rm in unique_rms:
            entries = mongo_handler.get_rejection_details_by_month_and_item(year, month, rm)
            if not entries:
                continue  # skip if no entries for this RM

            total_ok_parts = sum(float(e.get("ok_parts", 0) or 0) for e in entries)
            total_rejection = sum(float(e.get("rejections", 0) or 0) for e in entries)
            total_lumps = sum(float(e.get("lumps", 0) or 0) for e in entries)
            total_runner = sum(float(e.get("runner", 0) or 0) for e in entries)
            total_issued = sum(float(e.get("issued", 0) or 0) for e in entries)

            total_scrap_rej_lump = total_rejection + total_lumps
            percentage_rej_lump = total_scrap_rej_lump / total_issued if total_issued else 0
            total_scrap_rej_lump_runner = total_scrap_rej_lump + total_runner
            different = total_issued - (total_ok_parts + total_scrap_rej_lump_runner)

            formatted_records = []
            for e in entries:
                scrap_sum = float(e.get("rejections", 0) or 0) + float(e.get("lumps", 0) or 0) + float(e.get("runner", 0) or 0)
                e["scrap_sum"] = scrap_sum
                formatted_records.append(e)

            rm_wise_results.append({
                "rm": rm,
                "total_ok_parts": total_ok_parts,
                "total_rejection": total_rejection,
                "total_lumps": total_lumps,
                "total_runner": total_runner,
                "total_issued": total_issued,
                "total_scrap_sum_Rej_Lump": total_scrap_rej_lump,
                "percentage_rej_lump": percentage_rej_lump,
                "total_scrap_Rej_Lump_Runner": total_scrap_rej_lump_runner,
                "different": different,
                # "records": formatted_records
            })

        return {
            "message": "RM-wise monthly rejection details",
            "year": year,
            "month": month,
            "rm_wise_summary": rm_wise_results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



#######################################  DELETE REJECTION RECORDS  ###########################################


@router.delete("/delete_rejection_detail/{year}/{month}", response_model=dict)
def delete_rejection_detail(params: YearMonthValidator = Depends(), current_user: User = Depends(production_required)):
    try:
        month, year = params.month, params.year
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        # Direct MongoDB delete
        result = mongo_handler.rejection_detail_collection.delete_many({
            "timestamp": {"$gte": start_date, "$lt": end_date}
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="No records found for given month and year")

        return {"message": f"Deleted {result.deleted_count} rejection detail(s) for {month}/{year}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


