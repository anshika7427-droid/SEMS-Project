from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, date
from app.models import Subject, Milestone, Resource
import logging

logger = logging.getLogger("ai_engine")

# Preset resource recommendations based on subject keywords or general categories
PRESET_RESOURCES = [
    {
        "keywords": ["math", "algebra", "calculus", "linear", "geometry"],
        "resources": [
            {"title": "Khan Academy - Calculus & Algebra", "link": "https://www.khanacademy.org/math"},
            {"title": "Paul's Online Math Notes", "link": "https://tutorial.math.lamar.edu/"},
            {"title": "MIT OpenCourseWare - Mathematics", "link": "https://ocw.mit.edu/courses/mathematics/"}
        ]
    },
    {
        "keywords": ["computer", "programming", "python", "java", "coding", "software", "data", "algorithm"],
        "resources": [
            {"title": "GeeksforGeeks - Computer Science", "link": "https://www.geeksforgeeks.org/"},
            {"title": "freeCodeCamp - Programming Tutorials", "link": "https://www.freecodecamp.org/"},
            {"title": "LeetCode - Coding Practice", "link": "https://leetcode.com/"}
        ]
    },
    {
        "keywords": ["physics", "mechanics", "thermodynamics", "quantum"],
        "resources": [
            {"title": "HyperPhysics - Georgia State University", "link": "http://hyperphysics.phy-astr.gsu.edu/hbase/hframe.html"},
            {"title": "Physics Classroom", "link": "https://www.physicsclassroom.com/"}
        ]
    },
    {
        "keywords": ["chemistry", "organic", "inorganic", "biochem"],
        "resources": [
            {"title": "ChemGuide - Chemistry Reference", "link": "https://www.chemguide.co.uk/"},
            {"title": "CrashCourse Chemistry - YouTube", "link": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtPHzzYuWy6fYEaX9mQQ8oGr"}
        ]
    }
]

DEFAULT_RESOURCES = [
    {"title": "Google Scholar - Academic Papers", "link": "https://scholar.google.com"},
    {"title": "Crash Course - Study Skills", "link": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtNcAJRf3bN1IJu1tWRur28o"},
    {"title": "Wolfram Alpha - Computational Engine", "link": "https://www.wolframalpha.com"}
]

async def get_ai_recommendations(user_id: int, db: AsyncSession) -> dict:
    logger.info(f"Generating AI recommendations for User ID: {user_id}")
    
    subjects_res = await db.execute(select(Subject).where(Subject.user_id == user_id))
    subjects = subjects_res.scalars().all()
    milestones_res = await db.execute(select(Milestone).where(Milestone.user_id == user_id))
    milestones = milestones_res.scalars().all()
    
    if not subjects:
        return {
            "focus_insight": "Please add subjects to receive AI recommendations.",
            "subject_tips": [],
            "recommended_links": DEFAULT_RESOURCES
        }
        
    # Analyze workload
    hard_count = sum(1 for s in subjects if s.difficulty == "Hard")
    total_count = len(subjects)
    
    # Generate overall focus insight
    focus_insight = ""
    upcoming_milestones = []
    today = date.today()
    
    for m in milestones:
        try:
            exam_date = m.exam_date
            days_left = (exam_date - today).days
            if 0 <= days_left <= 7:
                upcoming_milestones.append((m.subject_name, days_left))
        except Exception as e:
            logger.error(f"Error parsing milestone exam date '{m.exam_date}': {e}")
            
    if upcoming_milestones:
        # Sort by urgency
        upcoming_milestones.sort(key=lambda x: x[1])
        urgent_sub, days = upcoming_milestones[0]
        if days == 0:
            focus_insight = f"🔴 URGENT: Your exam for {urgent_sub} is TODAY! Focus on light review and stay calm."
        elif days == 1:
            focus_insight = f"⚠️ CRITICAL: Your exam for {urgent_sub} is TOMORROW! Do active recall and review key summaries."
        else:
            focus_insight = f"⚡ Live Analysis: Your {urgent_sub} exam is in {days} days. We've optimized your schedule to prioritize prep time."
    elif hard_count / total_count > 0.5:
        focus_insight = "📈 Routine Constraint: You have a high ratio of Hard subjects. We recommend shorter, highly-focused study blocks."
    else:
        focus_insight = f"✅ Live Analysis: Workload is balanced with {total_count} subjects. Keep up the consistent study routine!"

    # Subject-wise study tips and recommended links
    subject_tips = []
    recommended_links = []
    seen_links = set()
    
    for s in subjects:
        # Determine technique
        technique = "Feynman Technique & Active Recall"
        if s.difficulty == "Hard":
            technique = "Spaced Repetition (Anki) & Pomodoro (50/10 intervals)"
        elif s.difficulty == "Medium":
            technique = "Pomodoro Technique (25/5 intervals) & Practice Questions"
            
        tip = f"For {s.name} ({s.difficulty}): Use {technique} to optimize memory retention."
        subject_tips.append(tip)
        
        # Match resources based on keywords in subject name
        name_lower = s.name.lower()
        matched = False
        for preset in PRESET_RESOURCES:
            if any(k in name_lower for k in preset["keywords"]):
                for res in preset["resources"]:
                    if res["link"] not in seen_links:
                        recommended_links.append(res)
                        seen_links.add(res["link"])
                matched = True
                
        if not matched:
            # Fallback to general academic resources
            for res in DEFAULT_RESOURCES:
                if res["link"] not in seen_links:
                    recommended_links.append(res)
                    seen_links.add(res["link"])
                    
    return {
        "focus_insight": focus_insight,
        "subject_tips": subject_tips,
        "recommended_links": recommended_links[:5] # limit to top 5 links
    }
