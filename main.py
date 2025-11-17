import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Literal
from datetime import datetime, timezone
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Student as StudentSchema, Lesson as LessonSchema, Homework as HomeworkSchema, Submission as SubmissionSchema, Message as MessageSchema

app = FastAPI(title="Mama Eidah API", description="منصة ماما عيدة التعليمية - عربية بالكامل")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEACHER_CODE = os.getenv("TEACHER_CODE", "9999")

# -------------------- Helpers --------------------

def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="معرّف غير صالح")


def serialize(doc: dict):
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id"))
    # convert datetimes to iso
    for k, v in list(doc.items()):
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc


# -------------------- Root & Health --------------------
@app.get("/")
def read_root():
    return {"message": "مرحباً بك في واجهة ماما عيدة الخلفية"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# -------------------- Auth --------------------
class LoginRequest(BaseModel):
    code: str

class LoginResponse(BaseModel):
    role: Literal["teacher", "student"]
    student: Optional[dict] = None

@app.post("/api/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    code = req.code.strip()
    if code == TEACHER_CODE:
        return {"role": "teacher"}
    # check student by code
    student = db["student"].find_one({"code": code})
    if student:
        return {"role": "student", "student": serialize(student)}
    raise HTTPException(status_code=404, detail="لم يتم العثور على المستخدم")

# -------------------- Students --------------------
@app.get("/api/students")
def list_students():
    students = db["student"].find().sort("created_at", -1)
    return [serialize(s) for s in students]

@app.post("/api/students")
def add_student(student: StudentSchema):
    # ensure unique code
    if db["student"].find_one({"code": student.code}):
        raise HTTPException(status_code=400, detail="رمز الدخول مستخدم بالفعل")
    inserted_id = create_document("student", student)
    saved = db["student"].find_one({"_id": ObjectId(inserted_id)})
    return serialize(saved)

@app.put("/api/students/{student_id}")
def update_student(student_id: str, data: StudentSchema):
    if db["student"].find_one({"code": data.code, "_id": {"$ne": oid(student_id)}}):
        raise HTTPException(status_code=400, detail="رمز الدخول مستخدم بالفعل")
    res = db["student"].update_one({"_id": oid(student_id)}, {"$set": {**data.model_dump(), "updated_at": datetime.now(timezone.utc)}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    return serialize(db["student"].find_one({"_id": oid(student_id)}))

@app.delete("/api/students/{student_id}")
def delete_student(student_id: str):
    _id = oid(student_id)
    # cascade delete
    db["lesson"].delete_many({"student_id": student_id})
    # delete homework and related submissions
    hws = list(db["homework"].find({"student_id": student_id}, {"_id": 1}))
    for hw in hws:
        db["submission"].delete_many({"homework_id": str(hw["_id"])})
    db["homework"].delete_many({"student_id": student_id})
    db["message"].delete_many({"student_id": student_id})
    res = db["student"].delete_one({"_id": _id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    return {"ok": True}

# -------------------- Lessons --------------------
@app.get("/api/lessons")
def list_lessons(student_id: Optional[str] = None):
    q = {"student_id": student_id} if student_id else {}
    lessons = db["lesson"].find(q).sort([("date", 1), ("start_time", 1)])
    return [serialize(l) for l in lessons]

@app.post("/api/lessons")
def add_lesson(lesson: LessonSchema):
    inserted_id = create_document("lesson", lesson)
    saved = db["lesson"].find_one({"_id": ObjectId(inserted_id)})
    return serialize(saved)

@app.put("/api/lessons/{lesson_id}")
def update_lesson(lesson_id: str, data: LessonSchema):
    res = db["lesson"].update_one({"_id": oid(lesson_id)}, {"$set": {**data.model_dump(), "updated_at": datetime.now(timezone.utc)}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="الدرس غير موجود")
    return serialize(db["lesson"].find_one({"_id": oid(lesson_id)}))

@app.delete("/api/lessons/{lesson_id}")
def delete_lesson(lesson_id: str):
    res = db["lesson"].delete_one({"_id": oid(lesson_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الدرس غير موجود")
    return {"ok": True}

# -------------------- Homework --------------------
@app.get("/api/homework")
def list_homework(student_id: Optional[str] = None):
    q = {"student_id": student_id} if student_id else {}
    items = db["homework"].find(q).sort("due_date", 1)
    return [serialize(x) for x in items]

@app.post("/api/homework")
def add_homework(hw: HomeworkSchema):
    inserted_id = create_document("homework", hw)
    saved = db["homework"].find_one({"_id": ObjectId(inserted_id)})
    return serialize(saved)

@app.put("/api/homework/{hw_id}")
def update_homework(hw_id: str, data: HomeworkSchema):
    res = db["homework"].update_one({"_id": oid(hw_id)}, {"$set": {**data.model_dump(), "updated_at": datetime.now(timezone.utc)}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="الواجب غير موجود")
    return serialize(db["homework"].find_one({"_id": oid(hw_id)}))

@app.delete("/api/homework/{hw_id}")
def delete_homework(hw_id: str):
    # delete submissions
    db["submission"].delete_many({"homework_id": hw_id})
    res = db["homework"].delete_one({"_id": oid(hw_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الواجب غير موجود")
    return {"ok": True}

# -------------------- Submissions (upload simplified as URL/base64 string) --------------------
class SubmitRequest(BaseModel):
    file_url: Optional[str] = None

@app.get("/api/submissions")
def list_submissions(student_id: Optional[str] = None, homework_id: Optional[str] = None):
    q = {}
    if student_id:
        q["student_id"] = student_id
    if homework_id:
        q["homework_id"] = homework_id
    items = db["submission"].find(q).sort("created_at", -1)
    return [serialize(x) for x in items]

@app.post("/api/homework/{hw_id}/submit")
def submit_homework(hw_id: str, student_id: str, body: SubmitRequest):
    hw = db["homework"].find_one({"_id": oid(hw_id)})
    if not hw:
        raise HTTPException(status_code=404, detail="الواجب غير موجود")
    data = SubmissionSchema(
        homework_id=hw_id,
        student_id=student_id,
        file_url=body.file_url,
        submitted_at=datetime.now(timezone.utc).isoformat(),
        status="submitted"
    )
    inserted_id = create_document("submission", data)
    # update homework status to submitted
    db["homework"].update_one({"_id": oid(hw_id)}, {"$set": {"status": "submitted", "updated_at": datetime.now(timezone.utc)}})
    saved = db["submission"].find_one({"_id": ObjectId(inserted_id)})
    return serialize(saved)

class GradeRequest(BaseModel):
    grade: float
    feedback: Optional[str] = None

@app.put("/api/submissions/{sub_id}/grade")
def grade_submission(sub_id: str, body: GradeRequest):
    res = db["submission"].update_one({"_id": oid(sub_id)}, {"$set": {"grade": body.grade, "feedback": body.feedback, "status": "graded", "updated_at": datetime.now(timezone.utc)}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="التسليم غير موجود")
    sub = db["submission"].find_one({"_id": oid(sub_id)})
    # also set homework to graded
    db["homework"].update_one({"_id": oid(sub["homework_id"])}, {"$set": {"status": "graded", "updated_at": datetime.now(timezone.utc)}})
    return serialize(sub)

# -------------------- Messages --------------------
@app.get("/api/messages")
def list_messages(student_id: str):
    msgs = db["message"].find({"student_id": student_id}).sort("created_at", 1)
    return [serialize(m) for m in msgs]

class NewMessage(BaseModel):
    student_id: str
    sender: Literal["teacher", "student"]
    text: str

@app.post("/api/messages")
def send_message(msg: NewMessage):
    inserted_id = create_document("message", MessageSchema(**msg.model_dump()))
    saved = db["message"].find_one({"_id": ObjectId(inserted_id)})
    return serialize(saved)

@app.put("/api/messages/{msg_id}/read")
def mark_read(msg_id: str):
    res = db["message"].update_one({"_id": oid(msg_id)}, {"$set": {"read": True, "updated_at": datetime.now(timezone.utc)}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
    return {"ok": True}

# -------------------- Simple Arabic AI Helper (rule-based) --------------------
class AIRequest(BaseModel):
    question: str

@app.post("/api/ai/chat")
def ai_chat(req: AIRequest):
    q = req.question.strip()
    # very simple rule-based responses for MVP
    tips = [
        "تذكّر أن تقرأ السؤال بهدوء وتحدد المطلوب أولاً.",
        "حاول أن تكتب خطوات الحل واحدة تلو الأخرى.",
        "أحسنت! يمكنك المحاولة مرة أخرى إذا أخطأت، التعلم ممتع.",
    ]
    if any(k in q for k in ["جمع", "طرح", "ضرب", "قسمة", "حساب"]):
        answer = "في الرياضيات: استخدم أمثلة بسيطة، وجرب الحل على أعداد صغيرة أولاً."
    elif any(k in q for k in ["قراءة", "إملاء", "قصة", "نص"]):
        answer = "للفهم: اقرأ الجملة ببطء، وابحث عن الكلمات المفتاحية، ثم أجب بجملة كاملة."
    elif any(k in q for k in ["علوم", "نبات", "حيوان", "جسم"]):
        answer = "في العلوم: فكّر ماذا يحدث أولاً ثم ماذا يحدث بعد ذلك. استخدم صورًا أو رسوماً تساعدك."
    else:
        answer = "أنا هنا لمساعدتك! أخبرني بالمطلوب وسأعطيك تلميحًا بسيطًا."
    return {
        "reply": f"مساعدة ماما عيدة: {answer}",
        "tip": tips[datetime.now().second % len(tips)]
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
