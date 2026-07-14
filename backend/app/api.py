from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AIReport, LearningDocument, PracticeSession, Question, Student, Textbook
from app.schemas import (
    DashboardResponse,
    DocumentConfirmRequest,
    OCRDemoRequest,
    PracticeDemoRequest,
    QuestionRead,
    ReportDemoRequest,
    StudentCreate,
    StudentRead,
    TextbookRead,
)

router = APIRouter()


@router.get("/health")
def api_health() -> dict[str, str]:
    return {"status": "ok", "service": "xueji-zhice-api"}


@router.get("/students", response_model=list[StudentRead])
def list_students(db: Session = Depends(get_db)) -> list[Student]:
    return list(db.scalars(select(Student).order_by(Student.created_at)).all())


@router.post("/students", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)) -> Student:
    student = Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/textbooks", response_model=list[TextbookRead])
def list_textbooks(
    subject: str | None = None,
    grade: int | None = None,
    db: Session = Depends(get_db),
) -> list[Textbook]:
    stmt = select(Textbook).where(Textbook.status == "active")
    if subject:
        stmt = stmt.where(Textbook.subject == subject)
    if grade:
        stmt = stmt.where(Textbook.grade == grade)
    return list(db.scalars(stmt.order_by(Textbook.subject, Textbook.publisher)).all())


@router.get("/questions", response_model=list[QuestionRead])
def list_questions(
    subject: str | None = None,
    grade: int | None = None,
    knowledge_point: str | None = None,
    db: Session = Depends(get_db),
) -> list[Question]:
    stmt = select(Question).where(Question.review_status == "active")
    if subject:
        stmt = stmt.where(Question.subject == subject)
    if grade:
        stmt = stmt.where(Question.grade == grade)
    if knowledge_point:
        stmt = stmt.where(Question.knowledge_point == knowledge_point)
    return list(db.scalars(stmt.order_by(Question.question_code)).all())


@router.post("/documents/demo-ocr", status_code=status.HTTP_201_CREATED)
def create_demo_ocr_document(payload: OCRDemoRequest, db: Session = Depends(get_db)) -> dict:
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    if payload.document_type == "score":
        raw_text = "数学 86分 班级平均分81分 排名12/36；英语92分"
        structured = {
            "document_type": "score",
            "exam_name": {"value": "第六单元阶段测验", "confidence": 0.91},
            "scores": [
                {"subject": "数学", "score": 86, "full_score": 100, "confidence": 0.98},
                {"subject": "英语", "score": 92, "full_score": 100, "confidence": 0.97},
            ],
            "low_confidence_fields": ["exam_name"],
        }
    elif payload.document_type == "comment":
        raw_text = "课堂听讲认真，基础知识掌握较好，但应用题容易忽略条件，订正需要及时。"
        structured = {
            "document_type": "comment",
            "original_text": raw_text,
            "labels": [
                {"dimension": "课堂专注", "level": "良好", "evidence": "课堂听讲认真", "confidence": 0.96},
                {"dimension": "基础知识", "level": "较好", "evidence": "基础知识掌握较好", "confidence": 0.94},
                {"dimension": "迁移应用", "level": "需要加强", "evidence": "应用题容易忽略条件", "confidence": 0.91},
                {"dimension": "订正习惯", "level": "需要改进", "evidence": "订正需要及时", "confidence": 0.86},
            ],
            "low_confidence_fields": ["labels.3"],
        }
    else:
        raw_text = "五年级上册 第六单元 多边形的面积"
        structured = {
            "document_type": payload.document_type,
            "grade": {"value": 5, "confidence": 0.95},
            "volume": {"value": "上册", "confidence": 0.97},
            "unit": {"value": "第六单元", "confidence": 0.92},
            "topic": {"value": "多边形的面积", "confidence": 0.94},
            "low_confidence_fields": [],
        }

    document = LearningDocument(
        student_id=payload.student_id,
        uploaded_by_role=payload.uploaded_by_role,
        document_type=payload.document_type,
        file_name=payload.file_name,
        status="awaiting_confirmation",
        ocr_confidence=0.94,
        ocr_raw_text=raw_text,
        structured_data=structured,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return {
        "data": {
            "id": document.id,
            "status": document.status,
            "ocr_confidence": document.ocr_confidence,
            "ocr_raw_text": document.ocr_raw_text,
            "structured_data": document.structured_data,
            "requires_parent_confirmation": payload.uploaded_by_role == "student",
        }
    }


@router.post("/documents/{document_id}/confirm")
def confirm_document(
    document_id: str,
    payload: DocumentConfirmRequest,
    db: Session = Depends(get_db),
) -> dict:
    document = db.get(LearningDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="资料不存在")
    if document.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail="当前资料状态不允许确认")
    document.confirmed_data = payload.confirmed_data
    document.status = "confirmed"
    document.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    return {"data": {"id": document.id, "status": document.status}}


@router.post("/practice-sessions/demo", status_code=status.HTTP_201_CREATED)
def create_demo_practice(payload: PracticeDemoRequest, db: Session = Depends(get_db)) -> dict:
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    stmt = (
        select(Question)
        .where(
            Question.review_status == "active",
            Question.subject == payload.subject,
            Question.knowledge_point == payload.knowledge_point,
        )
        .limit(payload.question_count)
    )
    questions = list(db.scalars(stmt).all())
    if not questions:
        raise HTTPException(status_code=404, detail="本地题库中没有匹配题目")

    session = PracticeSession(
        student_id=payload.student_id,
        practice_type="targeted",
        subject=payload.subject,
        knowledge_point=payload.knowledge_point,
        question_ids=[q.id for q in questions],
        total_count=len(questions),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "data": {
            "session_id": session.id,
            "status": session.status,
            "question_count": session.total_count,
            "questions": [QuestionRead.model_validate(q).model_dump() for q in questions],
        }
    }


@router.post("/reports/demo", status_code=status.HTTP_201_CREATED)
def create_demo_report(payload: ReportDemoRequest, db: Session = Depends(get_db)) -> dict:
    student = db.get(Student, payload.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    metrics = {
        "weekly_minutes": 258,
        "effective_practice_minutes": 166,
        "task_completion_rate": 0.86,
        "math_basic_accuracy": 0.91,
        "math_application_accuracy": 0.58,
        "english_accuracy": 0.88,
    }

    if payload.report_type == "student":
        output = {
            "summary": "整体保持稳定进步，基础题表现很好。",
            "progress": ["英语练习正确率达到88%", "数学基础计算正确率达到91%"],
            "strengths": ["基础计算", "英语词汇"],
            "challenges": ["数学应用题审题"],
            "next_tasks": [{"title": "每天4道分数应用题", "minutes": 15}],
            "method_tip": "先圈条件，再写数量关系，最后计算。",
            "encouragement": "你已经连续多次主动检查条件，这是很具体的进步。",
            "insufficient_data": ["作文", "口语"],
        }
    else:
        output = {
            "executive_summary": "孩子整体稳定进步，不建议增加总学习时长。数学应用题仍是两周内的主要改进方向。",
            "data_quality": {"level": "medium", "limitations": ["作文和口语数据不足"]},
            "dimensions": [
                {"name": "知识掌握", "score": 81},
                {"name": "学习执行", "score": 86},
                {"name": "迁移应用", "score": 68},
                {"name": "学习稳定", "score": 84},
            ],
            "strengths": ["英语", "数学基础计算", "任务执行"],
            "issues": ["数学应用题审题", "订正及时性"],
            "two_week_actions": [
                {"action": "每天15分钟应用题专项", "measure": "复测达到80%"},
                {"action": "保持总学习时长不变", "measure": "有效练习占比不低于60%"},
            ],
            "parent_communication": ["只提醒孩子先写数量关系，不直接提示答案"],
            "insufficient_data": ["作文", "口语"],
        }

    report = AIReport(
        student_id=payload.student_id,
        report_type=payload.report_type,
        metrics=metrics,
        output_json=output,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"data": {"report_id": report.id, "status": report.status, "metrics": metrics, "report": output}}


@router.get("/dashboard/{role}", response_model=DashboardResponse)
def get_dashboard(role: str, db: Session = Depends(get_db)) -> DashboardResponse:
    if role not in {"student", "parent", "admin"}:
        raise HTTPException(status_code=400, detail="不支持的角色")

    student = db.scalar(select(Student).order_by(Student.created_at))
    profile = {
        "student_id": student.id if student else None,
        "student_name": student.nickname if student else "未创建学生",
        "grade": student.current_grade if student else None,
        "term": student.current_term if student else None,
    }

    if role == "student":
        metrics = [
            {"label": "连续学习", "value": "12天", "trend": "+2天"},
            {"label": "成长星", "value": "1,260", "trend": "+180"},
            {"label": "任务完成率", "value": "86%", "trend": "+6%"},
            {"label": "综合学习指数", "value": "82", "trend": "+4"},
        ]
        tasks = [
            {"title": "数学分数应用题", "type": "重点", "minutes": 15},
            {"title": "语文概括段意", "type": "巩固", "minutes": 12},
            {"title": "英语单词闪卡", "type": "完成", "minutes": 5},
        ]
        notices = [{"title": "AI提示", "content": "先圈出条件，再写数量关系。"}]
    elif role == "parent":
        metrics = [
            {"label": "本周使用时间", "value": "4h18m", "trend": "+32m"},
            {"label": "有效做题时间", "value": "2h46m", "trend": "64%"},
            {"label": "任务完成率", "value": "86%", "trend": "18/21"},
            {"label": "待确认资料", "value": "2份", "trend": "需处理"},
        ]
        tasks = [
            {"title": "确认阶段成绩单", "type": "OCR确认", "minutes": 2},
            {"title": "推送数学专项", "type": "家长操作", "minutes": 1},
        ]
        notices = [{"title": "本周结论", "content": "保持总学习时长，把重复基础题替换为应用题。"}]
    else:
        metrics = [
            {"label": "系统用户", "value": "1,286", "trend": "+18"},
            {"label": "AI报告成功率", "value": "99.2%", "trend": "正常"},
            {"label": "今日OCR页数", "value": "864", "trend": "评语为主"},
            {"label": "本地题库", "value": "268K", "trend": "89.9%已审核"},
        ]
        tasks = [
            {"title": "复核高频争议题", "type": "题库", "minutes": 20},
            {"title": "检查OCR手写延迟", "type": "运维", "minutes": 10},
        ]
        notices = [{"title": "MVP边界", "content": "教师端、整张试卷OCR和纸质错题提取均未开放。"}]

    return DashboardResponse(role=role, profile=profile, metrics=metrics, tasks=tasks, notices=notices)
