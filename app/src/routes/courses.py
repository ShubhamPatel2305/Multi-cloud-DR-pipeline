from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.config import get_settings
from src.db import db

router = APIRouter(prefix="/api/courses", tags=["courses"])


class Course(BaseModel):
    code: str = Field(min_length=3, max_length=24)
    title: str
    instructor: str
    seats: int = Field(ge=0)


class CourseRead(Course):
    id: str
    created_at: datetime
    served_by: str


@router.get("", response_model=list[CourseRead])
async def list_courses(limit: int = 20):
    settings = get_settings()
    cursor = db().courses.find().sort("created_at", -1).limit(limit)
    out: list[CourseRead] = []
    async for doc in cursor:
        out.append(
            CourseRead(
                id=str(doc["_id"]),
                code=doc["code"],
                title=doc["title"],
                instructor=doc["instructor"],
                seats=doc["seats"],
                created_at=doc["created_at"],
                served_by=settings.region_id,
            )
        )
    return out


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
async def create_course(course: Course):
    settings = get_settings()
    doc = course.model_dump()
    doc["created_at"] = datetime.now(timezone.utc)

    result = await db().courses.insert_one(doc)
    return CourseRead(
        id=str(result.inserted_id),
        **course.model_dump(),
        created_at=doc["created_at"],
        served_by=settings.region_id,
    )


@router.get("/{code}", response_model=CourseRead)
async def get_course(code: str):
    settings = get_settings()
    doc = await db().courses.find_one({"code": code})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="course not found")
    return CourseRead(
        id=str(doc["_id"]),
        code=doc["code"],
        title=doc["title"],
        instructor=doc["instructor"],
        seats=doc["seats"],
        created_at=doc["created_at"],
        served_by=settings.region_id,
    )
