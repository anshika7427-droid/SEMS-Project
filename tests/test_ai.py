import pytest
from datetime import datetime, date, timedelta
from sqlalchemy import select
from app.models import User, Subject, Milestone, ScheduleEvent, StudySession
from app.scheduler import generate_weekly_schedule, calculate_priority
from app.ai_engine import get_ai_recommendations
from app.analytics import get_user_analytics

async def test_scheduler_algorithm(db):
    # Setup test user
    user = User(name="Test User", email="test@example.com", password="hash")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Setup subjects
    math = Subject(name="Math", difficulty="Hard", user_id=user.id)
    english = Subject(name="English", difficulty="Easy", user_id=user.id)
    db.add_all([math, english])
    await db.commit()

    # Setup milestone
    exam_date = date.today() + timedelta(days=5)
    milestone = Milestone(
        subject_id=math.id,
        subject_name="Math",
        exam_date=exam_date,
        user_id=user.id
    )
    db.add(milestone)
    await db.commit()

    # Verify priority calculation
    milestones_list = [milestone]
    math_priority = calculate_priority(math, milestones_list)
    english_priority = calculate_priority(english, milestones_list)
    
    # Math should have a higher priority score due to Hard difficulty + upcoming exam
    assert math_priority > english_priority

    # Generate schedule
    events = await generate_weekly_schedule(user.id, db)
    assert len(events) > 0

    # Retrieve and check
    saved_events_res = await db.execute(select(ScheduleEvent).where(ScheduleEvent.user_id == user.id))
    saved_events = saved_events_res.scalars().all()
    assert len(saved_events) == len(events)
    # Math is harder and has an exam, so it should be represented in the schedule events
    subject_ids = [e.subject_id for e in saved_events]
    assert math.id in subject_ids

async def test_ai_insights_and_analytics(db):
    user = User(name="Test User", email="test@example.com", password="hash")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    math = Subject(name="Math", difficulty="Hard", user_id=user.id)
    db.add(math)
    await db.commit()

    # Log study sessions to check analytics
    today_str = datetime.now().strftime("%Y-%m-%d 10:00:00")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d 15:00:00")

    session_today = StudySession(
        user_id=user.id,
        subject_id=math.id,
        duration_minutes=60,
        completed_at=datetime.strptime(today_str, "%Y-%m-%d %H:%M:%S"),
        session_type="Pomodoro"
    )
    session_yesterday = StudySession(
        user_id=user.id,
        subject_id=math.id,
        duration_minutes=45,
        completed_at=datetime.strptime(yesterday_str, "%Y-%m-%d %H:%M:%S"),
        session_type="Pomodoro"
    )
    db.add_all([session_today, session_yesterday])
    await db.commit()

    # 1. Check Analytics
    analytics = await get_user_analytics(user.id, db)
    # Streak should be 2 days (today + yesterday consecutive)
    assert analytics["active_streak"] == 2
    # Weekly hours = (60+45)/60 = 1.75 -> rounded to 1.8 hours
    assert analytics["weekly_study_hours"] == 1.8
    # Check daily breakdown contains hours for today's day of week
    today_day_name = datetime.now().strftime("%A")
    assert analytics["weekly_days_hours"][today_day_name] == 1.0

    # 2. Check AI Engine Recommendations
    recs = await get_ai_recommendations(user.id, db)
    assert "focus_insight" in recs
    assert len(recs["subject_tips"]) > 0
    assert len(recs["recommended_links"]) > 0

async def test_grade_predictor_past_performance(db):
    from app.utils.grade_predictor import get_grade_prediction
    from app.models import User, Subject, Task
    import inspect
    import app.utils.grade_predictor as gp

    # 1. Assert hashlib is not in the source file of grade_predictor
    src = inspect.getsource(gp)
    assert "hashlib" not in src
    assert "md5" not in src

    # 2. Setup user and data
    user = User(name="AI User", email="ai@example.com", password="pwd")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 3. Predict grade with no subjects
    pred_init = await get_grade_prediction(user.id, db)
    pred_init2 = await get_grade_prediction(user.id, db)
    assert pred_init["predicted_score"] == pred_init2["predicted_score"]
    assert pred_init["grade_confidence"] == 55  # Base 85 - 10 (tasks) - 10 (milestones) - 10 (no completion rates) = 55

    # 4. Add subject and tasks to verify deterministic prediction based on real data
    sub = Subject(name="Programming", difficulty="Hard", user_id=user.id)
    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    t1 = Task(title="Task 1", priority="Medium", deadline=date.today(), status="Completed", subject_id=sub.id, user_id=user.id)
    t2 = Task(title="Task 2", priority="Medium", deadline=date.today(), status="Pending", subject_id=sub.id, user_id=user.id)
    db.add_all([t1, t2])
    await db.commit()

    pred_sub1 = await get_grade_prediction(user.id, db)
    pred_sub1_again = await get_grade_prediction(user.id, db)
    assert pred_sub1["predicted_score"] == pred_sub1_again["predicted_score"]
    
    # 5. Change subject name to "Chemistry" (which would have yielded a different MD5 hash)
    sub.name = "Chemistry"
    await db.commit()
    
    pred_sub2 = await get_grade_prediction(user.id, db)
    assert pred_sub1["predicted_score"] == pred_sub2["predicted_score"]
