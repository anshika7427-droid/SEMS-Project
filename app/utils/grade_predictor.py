from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, datetime, timedelta
from app.models import Task, Subject, Milestone, StudySession

async def get_grade_prediction(user_id: int, db: AsyncSession) -> dict:
    # 1. Task Completion
    total_tasks_res = await db.execute(select(func.count()).select_from(Task).where(Task.user_id == user_id))
    total_tasks = total_tasks_res.scalar_one()
    
    completed_tasks_res = await db.execute(
        select(func.count()).select_from(Task).where(Task.user_id == user_id, Task.status == "Completed")
    )
    completed_tasks = completed_tasks_res.scalar_one()
    
    task_completion = (completed_tasks / total_tasks * 100.0) if total_tasks > 0 else 85.0
    
    # 2. Milestone Completion
    milestones_res = await db.execute(select(Milestone).where(Milestone.user_id == user_id))
    milestones = milestones_res.scalars().all()
    
    milestone_completion = 80.0
    if milestones:
        milestone_completion = sum(m.completion_percentage for m in milestones) / len(milestones)
        
    # 3. Attendance (Consistency based on study sessions)
    # Let's count how many days the user studied in the last 7 days.
    sessions_res = await db.execute(select(StudySession).where(StudySession.user_id == user_id))
    sessions = sessions_res.scalars().all()
    
    study_days = set()
    today = date.today()
    for s in sessions:
        try:
            from app.utils.helpers import parse_date
            sess_date = parse_date(s.completed_at)
            if today - sess_date <= timedelta(days=7):
                study_days.add(sess_date)
        except Exception:
            pass
            
    # Mock realistic attendance: baseline 80% + active study streak/days study
    attendance = min(100.0, 75.0 + len(study_days) * 4.0)
    
    # 4. Past Performance / Previous Grade
    # Real past performance: average task completion rate across all subjects of the user.
    # It represents the average completion rate of tasks assigned to each of the user's subjects.
    subjects_res = await db.execute(select(Subject).where(Subject.user_id == user_id))
    subjects = subjects_res.scalars().all()
    
    subject_completion_rates = []
    for s in subjects:
        total_stmt = select(func.count(Task.id)).where(Task.user_id == user_id, Task.subject_id == s.id)
        done_stmt = select(func.count(Task.id)).where(Task.user_id == user_id, Task.subject_id == s.id, Task.status == "Completed")
        
        total_res = await db.execute(total_stmt)
        total = total_res.scalar_one()
        
        done_res = await db.execute(done_stmt)
        done = done_res.scalar_one()
        
        if total > 0:
            subject_completion_rates.append(done / total * 100.0)
            
    past_performance = sum(subject_completion_rates) / len(subject_completion_rates) if subject_completion_rates else 70.0
        
    # 5. Exam Readiness
    exam_readiness = milestone_completion
    critical_exam = False
    for m in milestones:
        try:
            from app.utils.helpers import parse_date
            exam_date = parse_date(m.exam_date)
            days_left = (exam_date - today).days
            if 0 <= days_left <= 3:
                critical_exam = True
                if m.completion_percentage < 60:
                    exam_readiness = max(0.0, exam_readiness - 15.0)
        except Exception:
            pass
            
    # 6. Formula
    current_score = (task_completion * 0.5 + milestone_completion * 0.5)
    
    predicted_score = (
        task_completion * 0.35 +
        milestone_completion * 0.25 +
        attendance * 0.20 +
        past_performance * 0.20
    )
    
    # Confidence logic
    confidence = 85
    if total_tasks < 3:
        confidence -= 10
    if len(milestones) < 2:
        confidence -= 10
    if not subject_completion_rates:
        confidence -= 10
    if critical_exam:
        confidence -= 5
    confidence = max(50, min(95, confidence))
    
    # Map scores to grades
    def get_grade_letter(s):
        if s >= 97: return "A+"
        if s >= 93: return "A"
        if s >= 90: return "A-"
        if s >= 87: return "B+"
        if s >= 83: return "B"
        if s >= 80: return "B-"
        if s >= 77: return "C+"
        if s >= 73: return "C"
        if s >= 70: return "C-"
        if s >= 60: return "D"
        return "F"
        
    current_grade = get_grade_letter(current_score)
    predicted_grade = get_grade_letter(predicted_score)
    
    # Strengths and Risks
    strengths = []
    risks = []
    
    if task_completion >= 80:
        strengths.append("High assignment completion")
    else:
        risks.append("Low assignment completion")
        
    if attendance >= 85:
        strengths.append("Strong attendance")
    else:
        risks.append("Irregular attendance")
        
    if milestone_completion >= 75:
        strengths.append("High milestone completion")
    else:
        risks.append("Low milestone completion")
        
    if past_performance >= 80:
        strengths.append("Strong past performance")
        
    if critical_exam and exam_readiness < 70:
        risks.append("Upcoming exams not prepared")
        
    # Default tips
    tip = "Complete tasks and keep your schedule active to raise your grade prediction."
    if risks:
        if "Upcoming exams not prepared" in risks:
            tip = "Allocate deep focus study blocks to subjects with exams this week."
        elif "Low milestone completion" in risks:
            tip = "Focus on completing your milestone targets to secure a higher grade."
        elif "Low assignment completion" in risks:
            tip = "Review and mark pending tasks as completed to raise your prediction."
    elif strengths:
        tip = "Excellent performance! Maintain your current routine to secure a top grade."
        
    return {
        "current_score": round(current_score, 1),
        "current_grade": current_grade,
        "predicted_score": round(predicted_score, 1),
        "predicted_grade": predicted_grade,
        "grade_confidence": confidence,
        "grade_strengths": strengths if strengths else ["Starting off strong"],
        "grade_risks": risks if risks else ["No major risks detected"],
        "grade_tip": tip
    }
