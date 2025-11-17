"""
Database Schemas for Mama Eidah Platform

Each Pydantic model corresponds to a MongoDB collection.
Collection name is the lowercase of the class name.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal

class Student(BaseModel):
    name: str = Field(..., description="اسم الطالب")
    gender: Literal["boy", "girl"] = Field(..., description="الجنس")
    grade: Literal["1", "2", "3"] = Field(..., description="الصف الدراسي")
    code: str = Field(..., description="رمز الدخول الرقمي")
    avatar: Literal["boy", "girl"] = Field(..., description="الصورة الرمزية")

class Lesson(BaseModel):
    student_id: str = Field(..., description="معرّف الطالب")
    date: str = Field(..., description="تاريخ الدرس (YYYY-MM-DD)")
    start_time: str = Field(..., description="وقت البداية (HH:MM)")
    topic: str = Field(..., description="موضوع الدرس")
    notes: Optional[str] = Field(None, description="ملاحظات اختيارية")
    status: Literal["scheduled", "completed", "cancelled", "rescheduled"] = Field("scheduled")

class Homework(BaseModel):
    student_id: str = Field(...)
    lesson_id: Optional[str] = Field(None)
    title: str = Field(...)
    description: Optional[str] = Field(None)
    due_date: Optional[str] = Field(None)
    attachment_url: Optional[str] = Field(None, description="رابط المرفق")
    status: Literal["pending", "submitted", "graded"] = Field("pending")

class Submission(BaseModel):
    homework_id: str = Field(...)
    student_id: str = Field(...)
    file_url: Optional[str] = Field(None)
    submitted_at: Optional[str] = Field(None)
    status: Literal["submitted", "graded"] = Field("submitted")
    grade: Optional[float] = Field(None)
    feedback: Optional[str] = Field(None)

class Message(BaseModel):
    student_id: str = Field(...)
    sender: Literal["teacher", "student"] = Field(...)
    text: str = Field(...)
    read: bool = Field(False)

class Auth(BaseModel):
    code: str = Field(..., description="رمز الدخول")
    role: Literal["teacher", "student"] = Field(...)
    student_id: Optional[str] = Field(None)
