from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Question, Student, Textbook


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(Student.id).limit(1)) is None:
        db.add(
            Student(
                nickname="林小雨",
                school_system="6-3",
                current_grade=5,
                current_term="2026-2027 第一学期",
                region="广东省广州市",
                daily_minutes_limit=50,
            )
        )

    if db.scalar(select(Textbook.id).limit(1)) is None:
        db.add_all(
            [
                Textbook(
                    subject="语文",
                    publisher="人民教育出版社",
                    version_name="统编版",
                    revision_year=2024,
                    grade=5,
                    volume="上册",
                ),
                Textbook(
                    subject="数学",
                    publisher="人民教育出版社",
                    version_name="人教版",
                    revision_year=2024,
                    grade=5,
                    volume="上册",
                ),
                Textbook(
                    subject="英语",
                    publisher="外语教学与研究出版社",
                    version_name="外研版",
                    revision_year=2024,
                    grade=5,
                    volume="上册",
                ),
            ]
        )

    if db.scalar(select(Question.id).limit(1)) is None:
        db.add_all(
            [
                Question(
                    question_code="Q-M5-102846",
                    subject="数学",
                    grade=5,
                    knowledge_point="分数应用题",
                    question_type="single_choice",
                    difficulty=2,
                    cognitive_level="application",
                    stem="一本书共有120页，小明第一天看了全书的1/4，第二天看了剩下部分的1/3。第二天看了多少页？",
                    options={"A": "20页", "B": "30页", "C": "40页", "D": "45页"},
                    answer={"selected": ["B"]},
                    explanation="第一天看30页，剩90页；第二天看90×1/3=30页。",
                    hints=["先求第一天看了多少页", "再求剩下多少页", "第二天看剩下部分的1/3"],
                    estimated_seconds=180,
                ),
                Question(
                    question_code="Q-M5-102847",
                    subject="数学",
                    grade=5,
                    knowledge_point="分数应用题",
                    question_type="single_choice",
                    difficulty=2,
                    cognitive_level="variant_application",
                    stem="一桶油有90千克，第一次用去1/3，第二次用去剩余的1/2。第二次用去多少千克？",
                    options={"A": "15千克", "B": "30千克", "C": "45千克", "D": "60千克"},
                    answer={"selected": ["B"]},
                    explanation="第一次用30千克，剩60千克；第二次用60×1/2=30千克。",
                    hints=["注意第二次的单位1是剩余部分"],
                    estimated_seconds=150,
                ),
                Question(
                    question_code="Q-E5-083521",
                    subject="英语",
                    grade=5,
                    knowledge_point="第三人称单数",
                    question_type="single_choice",
                    difficulty=1,
                    cognitive_level="understanding",
                    stem="She ___ to school on Monday.",
                    options={"A": "go", "B": "goes", "C": "going", "D": "went"},
                    answer={"selected": ["B"]},
                    explanation="一般现在时中，主语She是第三人称单数，动词go变为goes。",
                    hints=["观察主语是She"],
                    estimated_seconds=60,
                ),
            ]
        )

    db.commit()
