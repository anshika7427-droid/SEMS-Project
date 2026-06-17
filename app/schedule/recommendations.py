from sqlalchemy.orm import Session
from datetime import date, datetime
import logging
import math
import re
import hashlib
from typing import List, Dict, Tuple, Any

from app.models import Subject, Milestone, Task
from app.config import LLM_API_KEY
from app.services.llm_service import call_llm_api

logger = logging.getLogger("schedule.recommendations")

# Reference resources corpus
RESOURCE_LIBRARY = [
    {
        "title": "Khan Academy - Calculus & Algebra",
        "link": "https://www.khanacademy.org/math",
        "description": "Mathematics algebra calculus linear geometry equations functions math learning resources practice exercises derivatives integrals limits trigonometry"
    },
    {
        "title": "Paul's Online Math Notes",
        "link": "https://tutorial.math.lamar.edu/",
        "description": "Mathematics calculus algebra online math notes differential equations cheat sheets tutorials calculus I II III math review"
    },
    {
        "title": "MIT OpenCourseWare - Mathematics",
        "link": "https://ocw.mit.edu/courses/mathematics/",
        "description": "Mathematics courses linear algebra calculus statistics probability advanced math lecture notes video lectures"
    },
    {
        "title": "GeeksforGeeks - Computer Science",
        "link": "https://www.geeksforgeeks.org/",
        "description": "Computer science programming coding Python Java software engineering data structures algorithms database SQL web technology"
    },
    {
        "title": "freeCodeCamp - Programming Tutorials",
        "link": "https://www.freecodecamp.org/",
        "description": "Computer programming web development JavaScript Python HTML CSS coding bootcamp tutorials database SQL Git"
    },
    {
        "title": "LeetCode - Coding Practice",
        "link": "https://leetcode.com/",
        "description": "Programming coding practice interview preparation algorithms data structures python java c++ problem solving test cases"
    },
    {
        "title": "HyperPhysics - Georgia State University",
        "link": "http://hyperphysics.phy-astr.gsu.edu/hbase/hframe.html",
        "description": "Physics mechanics thermodynamics quantum electromagnetism light sound relativity astrophysics physics guide"
    },
    {
        "title": "Physics Classroom",
        "link": "https://www.physicsclassroom.com/",
        "description": "Physics tutorials mechanics waves electricity light physics worksheets lessons vectors force energy kinematics"
    },
    {
        "title": "ChemGuide - Chemistry Reference",
        "link": "https://www.chemguide.co.uk/",
        "description": "Chemistry organic inorganic physical biochemistry chemguide learning resources atoms bonding thermodynamics"
    },
    {
        "title": "CrashCourse Chemistry - YouTube",
        "link": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtPHzzYuWy6fYEaX9mQQ8oGr",
        "description": "Chemistry crashcourse organic inorganic atoms periodic table reactions biochemistry video tutorials molecules gases"
    },
    {
        "title": "Google Scholar - Academic Papers",
        "link": "https://scholar.google.com",
        "description": "Academic research paper scientific journal articles citation literature search scholarly database peer-reviewed publications"
    },
    {
        "title": "Crash Course - Study Skills",
        "link": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtNcAJRf3bN1IJu1tWRur28o",
        "description": "Study skills productivity note taking test taking organization time management active recall spaced repetition exams flashcards"
    },
    {
        "title": "Wolfram Alpha - Computational Engine",
        "link": "https://www.wolframalpha.com",
        "description": "Computational intelligence calculator calculus algebra math chemistry physics answers step-by-step solver plots equations units conversion"
    }
]

DEFAULT_RESOURCES = [
    {"title": "Google Scholar - Academic Papers", "link": "https://scholar.google.com"},
    {"title": "Crash Course - Study Skills", "link": "https://www.youtube.com/playlist?list=PL8dPuuaLjXtNcAJRf3bN1IJu1tWRur28o"},
    {"title": "Wolfram Alpha - Computational Engine", "link": "https://www.wolframalpha.com"}
]

# Simple In-Memory Cache for Recommendations
RECOMMENDATION_CACHE = {} # user_id -> {"state_hash": str, "timestamp": datetime, "data": dict}

def tokenize(text: str) -> List[str]:
    """Lowercase and extract words of length >= 2."""
    if not text:
        return []
    return re.findall(r'[a-z0-9]{2,}', text.lower())

class SimpleTFIDF:
    """Lightweight pure Python TF-IDF Vectorizer and Cosine Similarity matcher."""
    def __init__(self, documents: List[str]):
        self.num_docs = len(documents)
        self.doc_term_counts = []
        self.df = {}
        
        for doc in documents:
            tokens = tokenize(doc)
            term_counts = {}
            for token in tokens:
                term_counts[token] = term_counts.get(token, 0) + 1
            self.doc_term_counts.append(term_counts)
            for term in term_counts:
                self.df[term] = self.df.get(term, 0) + 1
                
        # Calculate IDF: log(1 + (N / (1 + DF)))
        self.idf = {}
        for term, df_val in self.df.items():
            self.idf[term] = math.log(1.0 + (self.num_docs / (1.0 + df_val)))
            
    def get_tfidf_vector(self, tokens: List[str]) -> Dict[str, float]:
        tf = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
            
        vector = {}
        for term, count in tf.items():
            if term in self.idf:
                vector[term] = count * self.idf[term]
        return vector

    @staticmethod
    def cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
        dot_product = 0.0
        for term, val in v1.items():
            if term in v2:
                dot_product += val * v2[term]
                
        m1 = math.sqrt(sum(val ** 2 for val in v1.values()))
        m2 = math.sqrt(sum(val ** 2 for val in v2.values()))
        
        if m1 == 0.0 or m2 == 0.0:
            return 0.0
            
        return dot_product / (m1 * m2)

# Instantiate global TF-IDF model for resources
RESOURCE_DOCS = [res["description"] for res in RESOURCE_LIBRARY]
TFIDF_MATCHER = SimpleTFIDF(RESOURCE_DOCS)

def compute_user_state_hash(subjects: List[Subject], tasks: List[Task], milestones: List[Milestone]) -> str:
    """Generate a unique SHA-256 hash representing the current academic state of the user."""
    state_parts = []
    
    # Add subjects state
    for s in sorted(subjects, key=lambda x: x.id):
        state_parts.append(f"s:{s.id}:{s.name}:{s.difficulty}")
        
    # Add tasks state
    for t in sorted(tasks, key=lambda x: x.id):
        state_parts.append(f"t:{t.id}:{t.title}:{t.status}:{t.deadline}")
        
    # Add milestones state
    for m in sorted(milestones, key=lambda x: x.id):
        state_parts.append(f"m:{m.id}:{m.subject_name}:{m.exam_date}")
        
    state_str = "|".join(state_parts)
    return hashlib.sha256(state_str.encode("utf-8")).hexdigest()

def get_rule_and_tfidf_recommendations(user_id: int, subjects: List[Subject], tasks: List[Task], milestones: List[Milestone]) -> dict:
    """Fallback recommendation algorithm using TF-IDF similarity mapping and rule-based insights."""
    logger.info(f"Generating TF-IDF & Rule-based recommendations for User ID: {user_id}")
    
    # 1. Generate focus insight (Rule-based workload audit)
    hard_count = sum(1 for s in subjects if s.difficulty == "Hard")
    total_count = len(subjects)
    
    focus_insight = ""
    upcoming_milestones = []
    today = date.today()
    
    for m in milestones:
        try:
            # Parse exam date safely
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    exam_date = datetime.strptime(m.exam_date.strip().split()[0].split('T')[0], "%Y-%m-%d").date()
                    days_left = (exam_date - today).days
                    if 0 <= days_left <= 7:
                        upcoming_milestones.append((m.subject_name, days_left))
                    break
                except Exception:
                    continue
        except Exception as e:
            logger.exception(f"Error checking milestone exam date for Milestone ID {m.id}: {e}")
            
    if upcoming_milestones:
        upcoming_milestones.sort(key=lambda x: x[1])
        urgent_sub, days = upcoming_milestones[0]
        if days == 0:
            focus_insight = f"🔴 URGENT: Your exam for {urgent_sub} is TODAY! Focus on light review and stay calm."
        elif days == 1:
            focus_insight = f"⚠️ CRITICAL: Your exam for {urgent_sub} is TOMORROW! Do active recall and review key summaries."
        else:
            focus_insight = f"⚡ Live Analysis: Your {urgent_sub} exam is in {days} days. We've optimized your schedule to prioritize prep time."
    elif total_count > 0 and (hard_count / total_count > 0.5):
        focus_insight = "📈 Routine Constraint: You have a high ratio of Hard subjects. We recommend shorter, highly-focused study blocks."
    else:
        focus_insight = f"✅ Live Analysis: Workload is balanced with {total_count} subjects. Keep up the consistent study routine!"

    # 2. Subject tips
    subject_tips = []
    for s in subjects:
        technique = "Feynman Technique & Active Recall"
        if s.difficulty == "Hard":
            technique = "Spaced Repetition (Anki) & Pomodoro (50/10 intervals)"
        elif s.difficulty == "Medium":
            technique = "Pomodoro Technique (25/5 intervals) & Practice Questions"
        tip = f"For {s.name} ({s.difficulty}): Use {technique} to optimize memory retention."
        subject_tips.append(tip)

    # 3. TF-IDF recommendation logic
    # Construct a query string out of subject names, task titles, task descriptions, and milestone subjects
    query_terms = []
    for s in subjects:
        query_terms.append(s.name)
    for t in tasks:
        query_terms.append(t.title)
        if t.description:
            query_terms.append(t.description)
    for m in milestones:
        query_terms.append(m.subject_name)
        
    query_str = " ".join(query_terms)
    query_tokens = tokenize(query_str)
    
    recommended_links = []
    
    if query_tokens:
        query_vector = TFIDF_MATCHER.get_tfidf_vector(query_tokens)
        
        # Calculate similarity with each resource doc
        scores = []
        for idx, res in enumerate(RESOURCE_LIBRARY):
            doc_tokens = tokenize(res["description"])
            doc_vector = TFIDF_MATCHER.get_tfidf_vector(doc_tokens)
            sim = SimpleTFIDF.cosine_similarity(query_vector, doc_vector)
            scores.append((idx, sim))
            
        # Sort by similarity descending
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Select links above a threshold, limit to top 5
        seen_links = set()
        for idx, sim in scores:
            if sim > 0.05 and len(recommended_links) < 5:
                res = RESOURCE_LIBRARY[idx]
                recommended_links.append({"title": res["title"], "link": res["link"]})
                seen_links.add(res["link"])
                
        # If we got fewer than 3 links, fill up with defaults
        if len(recommended_links) < 3:
            for res in DEFAULT_RESOURCES:
                if res["link"] not in seen_links and len(recommended_links) < 5:
                    recommended_links.append(res)
                    seen_links.add(res["link"])
    else:
        recommended_links = DEFAULT_RESOURCES[:5]
        
    return {
        "focus_insight": focus_insight,
        "subject_tips": subject_tips,
        "recommended_links": recommended_links
    }

def get_recommendations(user_id: int, db: Session) -> dict:
    """Generate recommendations for the user. Uses caching, and falls back to TF-IDF if LLM fails."""
    global RECOMMENDATION_CACHE
    
    # 1. Fetch user context
    subjects = db.query(Subject).filter(Subject.user_id == user_id).all()
    milestones = db.query(Milestone).filter(Milestone.user_id == user_id).all()
    tasks = db.query(Task).filter(Task.user_id == user_id).all()
    
    if not subjects:
        return {
            "focus_insight": "Please add subjects to receive recommendations.",
            "subject_tips": [],
            "recommended_links": DEFAULT_RESOURCES[:5]
        }
        
    # 2. Check Cache
    state_hash = compute_user_state_hash(subjects, tasks, milestones)
    cached_entry = RECOMMENDATION_CACHE.get(user_id)
    if cached_entry and cached_entry["state_hash"] == state_hash:
        # Cache hits
        logger.info(f"Recommendation cache HIT for User ID: {user_id}")
        return cached_entry["data"]
        
    logger.info(f"Recommendation cache MISS for User ID: {user_id}")
    
    # 3. Try LLM if configured
    data = None
    if LLM_API_KEY:
        try:
            logger.info(f"Attempting to generate LLM recommendations for User ID: {user_id}")
            
            subjects_info = [{"id": s.id, "name": s.name, "difficulty": s.difficulty} for s in subjects]
            tasks_info = [{"title": t.title, "status": t.status, "deadline": t.deadline} for t in tasks]
            milestones_info = [{"subject": m.subject_name, "exam_date": m.exam_date} for m in milestones]
            
            system_instruction = (
                "You are an expert student productivity mentor. Analyze the student's current academic status "
                "and generate study recommendations. You MUST return a valid JSON object only. Do NOT include markdown tags "
                "outside the JSON structure. The JSON object must have exactly these fields:\n"
                "{\n"
                "  \"focus_insight\": \"A single sentence summarizing the overall study workload focus warning or encouraging tip.\",\n"
                "  \"subject_tips\": [\"Specific tip for Subject A (Pomodoro duration, active recall advice, exam approach)\", \"Specific tip for Subject B\"],\n"
                "  \"recommended_links\": [{\"title\": \"Resource Title\", \"link\": \"Resource URL\"}, ...]\n"
                "}\n"
                "Ensure links are realistic (such as Khan Academy, LeetCode, GeeksforGeeks, Pauls Online Math Notes, Wolfram Alpha, MIT OpenCourseWare)."
            )
            
            user_prompt = (
                f"Subjects Tracked:\n{subjects_info}\n\n"
                f"Tasks:\n{tasks_info}\n\n"
                f"Upcoming Exams (Milestones):\n{milestones_info}\n\n"
                f"Please generate the personalized advice and select matching study links."
            )
            
            llm_result = call_llm_api(system_instruction, user_prompt)
            
            # Validate LLM structure
            if isinstance(llm_result, dict) and "focus_insight" in llm_result and "subject_tips" in llm_result and "recommended_links" in llm_result:
                # Limit links to top 5
                llm_result["recommended_links"] = llm_result["recommended_links"][:5]
                data = llm_result
                logger.info(f"Successfully generated LLM recommendations for User ID: {user_id}")
            else:
                logger.warning(f"LLM returned invalid keys for User ID {user_id}. Falling back to TF-IDF.")
        except Exception as e:
            logger.exception(f"LLM recommendations generation failed for User ID {user_id}: {e}")
            
    # 4. Fallback to TF-IDF & Rule-based
    if not data:
        data = get_rule_and_tfidf_recommendations(user_id, subjects, tasks, milestones)
        
    # 5. Store in Cache
    RECOMMENDATION_CACHE[user_id] = {
        "state_hash": state_hash,
        "timestamp": datetime.now(),
        "data": data
    }
    
    return data
