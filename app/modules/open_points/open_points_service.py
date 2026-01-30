from fastapi import HTTPException
from typing import List, Dict, Any
from bson import ObjectId
from datetime import datetime
from app.shared.timezone import get_ist_now

# Import Schemas
from app.core.schemas.open_points import (
    CreateProjectRequest, 
    CreatePointRequest, 
    UpdatePointRequest,
    AddMemberRequest, 
    RemoveMemberRequest, 
    AssignProjectsRequest,
    PointStatus,
)

class OpenPointsService:

    @staticmethod
    def _get_user_id(user_obj) -> str:
        """Exhaustively tries to find the User ID."""
        # 1. Check standard attributes
        if hasattr(user_obj, 'id') and user_obj.id is not None:
            return str(user_obj.id)
        
        if hasattr(user_obj, '_id') and user_obj._id is not None:
            return str(user_obj._id)

        # 2. Check internal __dict__
        if hasattr(user_obj, '__dict__'):
            internal_dict = user_obj.__dict__
            if '_id' in internal_dict and internal_dict['_id'] is not None:
                return str(internal_dict['_id'])
            if 'id' in internal_dict and internal_dict['id'] is not None:
                return str(internal_dict['id'])

        # 3. DATABASE FALLBACK
        if hasattr(user_obj, 'email'):
            email = user_obj.email
            if email:
                db_user = OpenPointsService.mongo_handler.user_collection.find_one({"email": email}, {"_id": 1})
                if db_user and "_id" in db_user:
                    return str(db_user["_id"])

        raise ValueError("User object has no valid ID field")

    @staticmethod
    async def verify_project_access(project_id: str, current_user) -> Dict[str, Any]:
        project = OpenPointsService.mongo_handler.get_project_by_id(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        user_id_str = OpenPointsService._get_user_id(current_user)
        owner_id_str = str(project["owner"])
        
        is_owner = owner_id_str == user_id_str
        is_member = any(str(m["user"]) == user_id_str for m in project.get("team_members", []))

        if not is_owner and not is_member:
            raise HTTPException(status_code=403, detail="Access Denied: You are not part of this project")

        user_role = "L4" if is_owner else next(
            (m["role"] for m in project["team_members"] if str(m["user"]) == user_id_str), None
        )

        return {"project": project, "user_role": user_role, "user_id": user_id_str}

    # === PROJECT LOGIC ===

    @staticmethod
    async def create_project(request: CreateProjectRequest, current_user):
        try:
            owner_user = OpenPointsService.mongo_handler.get_user_by_username(request.ownerUsername)
            
            if not owner_user:
                raise HTTPException(status_code=404, detail="Owner user not found")

            owner_id = ObjectId(owner_user["_id"])
            
            project_id = OpenPointsService.mongo_handler.create_open_point_project(
                name=request.name,
                description=request.description,
                owner_id=owner_id,
                team_members=[m.model_dump() for m in request.team_members]
            )
            
            return {"message": "Project created", "id": str(project_id)}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def get_my_projects(current_user):
        try:
            user_id_str = OpenPointsService._get_user_id(current_user)

            projects = list(OpenPointsService.mongo_handler.open_point_projects_collection.find({
                "$or": [
                    {"owner": ObjectId(user_id_str)},
                    {"team_members.user": ObjectId(user_id_str)}
                ]
            }))
            
            project_stats = []
            for p in projects:
                points = list(OpenPointsService.mongo_handler.open_points_collection.find({"project_id": p["_id"]}))
                
                red = sum(1 for pt in points if pt.get("status") == "Red")
                yellow = sum(1 for pt in points if pt.get("status") == "Yellow")
                orange = sum(1 for pt in points if pt.get("status") == "Orange")
                green = sum(1 for pt in points if pt.get("status") == "Green")
                
                my_points = [pt for pt in points if str(pt.get("responsible_person")) == user_id_str]
                my_red = sum(1 for pt in my_points if pt.get("status") == "Red")
                my_yellow = sum(1 for pt in my_points if pt.get("status") == "Yellow")
                my_orange = sum(1 for pt in my_points if pt.get("status") == "Orange")
                my_green = sum(1 for pt in my_points if pt.get("status") == "Green")
                
                p["_id"] = str(p["_id"])
                p["owner"] = str(p["owner"])
                for member in p.get("team_members", []):
                    if "user" in member:
                        member["user"] = str(member["user"])
                
                project_stats.append({
                    **p,
                    "stats": {"red": red, "yellow": yellow, "orange": orange, "green": green, "total": len(points)},
                    "myStats": {"red": my_red, "yellow": my_yellow, "orange": my_orange, "green": my_green, "total": len(my_points)}
                })
            
            return project_stats
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def get_project_details(projectId: str, current_user):
        access = await OpenPointsService.verify_project_access(projectId, current_user)
        project = access["project"]
        
        project["_id"] = str(project["_id"])
        project["owner"] = str(project["owner"])
        for member in project.get("team_members", []):
            if "user" in member: member["user"] = str(member["user"])
        
        return project

    @staticmethod
    async def add_member(projectId: str, request: AddMemberRequest, current_user):
        try:
            await OpenPointsService.verify_project_access(projectId, current_user)
            project = OpenPointsService.mongo_handler.get_project_by_id(projectId)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            added_count = 0
            skipped_count = 0
            errors = []

            for member_req in request.members:
                user = OpenPointsService.mongo_handler.user_collection.find_one({"name": member_req.username})
                
                if not user:
                    errors.append(f"User '{member_req.username}' not found")
                    continue

                user_id = str(user["_id"])
                is_member = any(str(m["user"]) == user_id for m in project.get("team_members", []))
                if is_member:
                    skipped_count += 1
                    continue
                
                OpenPointsService.mongo_handler.add_project_member(projectId, user_id, member_req.role)
                OpenPointsService.mongo_handler.user_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$addToSet": {"access_modules": "Open Points"}}
                )
                added_count += 1
            
            updated_project = OpenPointsService.mongo_handler.get_project_by_id(projectId)
            updated_project["_id"] = str(updated_project["_id"])
            updated_project["owner"] = str(updated_project["owner"])
            for member in updated_project.get("team_members", []):
                if "user" in member: member["user"] = str(member["user"])

            response_msg = f"Processed {len(request.members)} members. Added: {added_count}, Skipped: {skipped_count}."
            if errors:
                response_msg += f" Errors: {', '.join(errors)}"
                
            return {"message": response_msg, "project": updated_project}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def remove_member(projectId: str, request: RemoveMemberRequest, current_user):
        try:
            project = OpenPointsService.mongo_handler.get_project_by_id(projectId)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            user_id_str = OpenPointsService._get_user_id(current_user)
            
            if str(project["owner"]) != user_id_str:
                raise HTTPException(status_code=403, detail="Only project owner can remove members")

            removed_count = 0
            is_owner_errors = []

            for uid in request.userIds:
                if str(project["owner"]) == uid:
                    is_owner_errors.append(uid)
                    continue
                success = OpenPointsService.mongo_handler.remove_project_member(projectId, uid)
                if success:
                    removed_count += 1

            response_details = []
            response_details.append(f"Removed {removed_count} members successfully.")
            if is_owner_errors:
                response_details.append(f"Cannot remove project owners: {', '.join(is_owner_errors)}")

            return {"message": " | ".join(response_details)}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def delete_project(projectId: str, current_user):
        try:
            project = OpenPointsService.mongo_handler.get_project_by_id(projectId)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            user_id_str = OpenPointsService._get_user_id(current_user)
            
            if str(project["owner"]) != user_id_str:
                raise HTTPException(status_code=403, detail="Only project owner can delete the project")

            OpenPointsService.mongo_handler.open_points_collection.delete_many({"project_id": ObjectId(projectId)})
            OpenPointsService.mongo_handler.delete_project(projectId)
            
            return {"message": "Project and all associated points deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # === POINT LOGIC ===

    @staticmethod
    async def get_project_points(projectId: str, current_user):
        await OpenPointsService.verify_project_access(projectId, current_user)
        
        OpenPointsService.mongo_handler.open_points_collection.update_many(
            {
                "project_id": ObjectId(projectId),
                "status": {"$ne": "Green"},
                "target_date": {"$lt": get_ist_now()}
            },
            {"$set": {"status": "Red"}}
        )
        
        points = list(OpenPointsService.mongo_handler.open_points_collection.find({"project_id": ObjectId(projectId)}).sort([
            ("status", 1),
            ("target_date", 1)
        ]))
        
        for p in points:
            p["_id"] = str(p["_id"])
            p["project_id"] = str(p["project_id"])
            if p.get("responsible_person"):
                p["responsible_person"] = str(p["responsible_person"])
            if p.get("reviewer"):
                p["reviewer"] = str(p["reviewer"])
            
        return points

    @staticmethod
    async def create_point(request: CreatePointRequest, current_user):
        try:
            point_data = request.model_dump(exclude_none=True)
            if "project_id" in point_data:
                point_data["project_id"] = ObjectId(point_data["project_id"])
            if "responsible_person" in point_data and point_data["responsible_person"]:
                point_data["responsible_person"] = ObjectId(point_data["responsible_person"])
            if "reviewer" in point_data and point_data["reviewer"]:
                point_data["reviewer"] = ObjectId(point_data["reviewer"])
                
            point_id = OpenPointsService.mongo_handler.create_open_point(point_data)
            return {"message": "Point created", "id": point_id}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def update_point(pointId: str, request: UpdatePointRequest, current_user):
        try:
            point = OpenPointsService.mongo_handler.open_points_collection.find_one({"_id": ObjectId(pointId)})
            if not point:
                raise HTTPException(status_code=404, detail="Point not found")
            
            user_id = request.userId
            if not user_id:
                user_id = str(current_user.id)

            status_val = request.status
            evidence = request.evidence
            remarks = request.remarks
            
            update_data = {}
            if status_val and status_val != point.get("status"):
                update_data["status"] = status_val.value if isinstance(status_val, PointStatus) else status_val
                
                if status_val == PointStatus.GREEN or status_val == "Green":
                    update_data["completion_date"] = get_ist_now()
                
                new_history_entry = {
                    "action": f"Status changed to {status_val}",
                    "changed_by": ObjectId(user_id),
                    "remarks": remarks or "",
                    "timestamp": get_ist_now()
                }
                OpenPointsService.mongo_handler.open_points_collection.update_one(
                    {"_id": ObjectId(pointId)},
                    {"$push": {"history": new_history_entry}}
                )

            if evidence and len(evidence) > 0:
                evidence_list = [e.model_dump() if hasattr(e, 'model_dump') else e for e in evidence]
                OpenPointsService.mongo_handler.open_points_collection.update_one(
                    {"_id": ObjectId(pointId)},
                    {"$push": {"evidence": {"$each": evidence_list}}}
                )

            other_fields = request.model_dump(exclude_none=True, exclude={
                "userId", "status", "evidence", "history", "remarks"
            })
            
            for field in ["responsible_person", "reviewer", "project_id"]:
                if field in other_fields and other_fields[field]:
                    try:
                        other_fields[field] = ObjectId(other_fields[field])
                    except:
                        pass

            if other_fields:
                OpenPointsService.mongo_handler.open_points_collection.update_one(
                    {"_id": ObjectId(pointId)},
                    {"$set": other_fields}
                )

            if update_data:
                OpenPointsService.mongo_handler.open_points_collection.update_one(
                    {"_id": ObjectId(pointId)},
                    {"$set": update_data}
                )

            return {"message": "Point updated"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def delete_point(pointId: str, current_user):
        try:
            result = OpenPointsService.mongo_handler.open_points_collection.delete_one({"_id": ObjectId(pointId)})
            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Point not found")
            return {"message": "Point deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # === ANALYTICS ===

    @staticmethod
    async def get_analytics(current_user):
        try:
            user_id_str = OpenPointsService._get_user_id(current_user)
            
            projects = OpenPointsService.mongo_handler.open_point_projects_collection.distinct(
                "_id", 
                {
                    "$or": [
                        {"owner": ObjectId(user_id_str)}, 
                        {"team_members.user": ObjectId(user_id_str)}
                    ]
                }
            )
            
            pipeline = [
                {"$match": {"project_id": {"$in": projects}}},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]
            
            stats = list(OpenPointsService.mongo_handler.open_points_collection.aggregate(pipeline))
            return stats
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # === ASSIGNMENT HELPERS ===

    @staticmethod
    async def get_all_project_names(current_user):
        try:
            projects = list(OpenPointsService.mongo_handler.open_point_projects_collection.find({}, {"name": 1}))
            names = sorted([p["name"] for p in projects])
            return names
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def get_user_assigned_projects(username: str, current_user):
        try:
            dojo_user = OpenPointsService.mongo_handler.DOJO_collection.find_one({"user_info.full_name": username})
            if not dojo_user and ObjectId.is_valid(username):
                 dojo_user = OpenPointsService.mongo_handler.DOJO_collection.find_one({"_id": ObjectId(username)})
            
            if not dojo_user:
                raise HTTPException(status_code=404, detail="User not found")

            employee_id = dojo_user.get("employee_id")
            if not employee_id:
                raise HTTPException(status_code=404, detail="Employee ID missing")

            auth_user = OpenPointsService.mongo_handler.user_collection.find_one({"employee_id": employee_id})
            if not auth_user:
                 raise HTTPException(status_code=404, detail="User Auth record not found")

            projects = list(OpenPointsService.mongo_handler.open_point_projects_collection.find({
                "$or": [
                    {"owner": auth_user["_id"]},
                    {"team_members.user": auth_user["_id"]}
                ]
            }, {"name": 1}))
            
            names = sorted([p["name"] for p in projects])
            return names
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def get_all_users():
        try:
            cursor = OpenPointsService.mongo_handler.DOJO_collection.find(
                {}, 
                {
                    "user_info.full_name": 1,
                    "_id": 1
                }
            )

            users_list = []
            for u in cursor:
                full_name = u.get("user_info", {}).get("full_name")
                
                if full_name:
                    users_list.append({
                        "full_name": full_name,
                        "id": str(u["_id"])
                    })

            return sorted(users_list, key=lambda x: (x["full_name"] or ""))

        except Exception as e:
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def assign_projects_to_user(username: str, request: AssignProjectsRequest, current_user):
        try:
            dojo_user = OpenPointsService.mongo_handler.DOJO_collection.find_one({"user_info.full_name": username})
            
            if not dojo_user and ObjectId.is_valid(username):
                dojo_user = OpenPointsService.mongo_handler.DOJO_collection.find_one({"_id": ObjectId(username)})
                
            if not dojo_user:
                raise HTTPException(status_code=404, detail="User not found in DOJO records")

            employee_id = dojo_user.get("employee_id")
            
            if not employee_id:
                raise HTTPException(status_code=404, detail="Employee ID missing in DOJO record")

            auth_user = OpenPointsService.mongo_handler.user_collection.find_one({"employee_id": employee_id})
            
            if not auth_user:
                auth_user = OpenPointsService.mongo_handler.user_collection.find_one({"email": dojo_user.get("user_info", {}).get("email")})
                
            if not auth_user:
                raise HTTPException(status_code=404, detail="Corresponding User record not found")

            user_id = auth_user["_id"]
            
            OpenPointsService.mongo_handler.open_point_projects_collection.update_many(
                {"team_members.user": user_id},
                {"$pull": {"team_members": {"user": user_id}}}
            )
            
            if request.projectNames and len(request.projectNames) > 0:
                OpenPointsService.mongo_handler.open_point_projects_collection.update_many(
                    {"name": {"$in": request.projectNames}},
                    {
                        "$addToSet": {
                            "team_members": {
                                "user": user_id,
                                "role": "L2", 
                                "added_at": get_ist_now()
                            }
                        }
                    }
                )
            
            return {"message": "Projects assigned successfully"}
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))