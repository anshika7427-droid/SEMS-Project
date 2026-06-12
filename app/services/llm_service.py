import json
import logging
import httpx
from app.config import LLM_API_KEY, LLM_MODEL, LLM_API_URL

logger = logging.getLogger("llm_service")

def validate_schedule_json(data: dict) -> bool:
    """
    Validates that the returned data is a dict containing a 'schedule' key
    whose value is a list of items matching the required structure.
    """
    if not isinstance(data, dict) or "schedule" not in data:
        logger.warning("Validation failed: Root key 'schedule' is missing or not a dictionary.")
        return False
    
    schedule = data["schedule"]
    if not isinstance(schedule, list):
        logger.warning("Validation failed: 'schedule' is not a list.")
        return False
        
    for idx, item in enumerate(schedule):
        if not isinstance(item, dict):
            logger.warning(f"Validation failed: schedule item at index {idx} is not a dictionary.")
            return False
        # Check that the required keys exist
        required_keys = ("day", "subject", "hours", "reason")
        if not all(k in item for k in required_keys):
            missing = [k for k in required_keys if k not in item]
            logger.warning(f"Validation failed: schedule item at index {idx} is missing keys: {missing}")
            return False
        # Check types
        if not isinstance(item["day"], str) or not isinstance(item["subject"], str):
            logger.warning(f"Validation failed: 'day' or 'subject' at index {idx} is not a string.")
            return False
        if not isinstance(item["hours"], (int, float)):
            logger.warning(f"Validation failed: 'hours' at index {idx} is not a number.")
            return False
        if not isinstance(item["reason"], str):
            logger.warning(f"Validation failed: 'reason' at index {idx} is not a string.")
            return False
            
    return True

def generate_ai_schedule(
    user_id: int,
    subjects: list,
    milestones: list,
    analytics: dict,
    calibration: dict = None
) -> dict:
    """
    Generates a personalized weekly study timetable using the configured LLM.
    Returns the parsed and validated JSON structure.
    """
    logger.info(f"Generating AI schedule for user {user_id} using model {LLM_MODEL}")
    
    if not LLM_API_KEY:
        logger.error("LLM_API_KEY is not set. Aborting LLM request.")
        raise ValueError("LLM_API_KEY is not configured.")
        
    # Compile list of subjects and difficulties
    subject_details = []
    for s in subjects:
        subject_details.append(f"- {s.name} (Difficulty: {s.difficulty or 'Medium'})")
    subjects_str = "\n".join(subject_details) if subject_details else "None"
    
    # Compile milestones
    milestone_details = []
    for m in milestones:
        milestone_details.append(f"- Exam for {m.subject_name} on {m.exam_date}")
    milestones_str = "\n".join(milestone_details) if milestone_details else "None"
    
    # Extract analytics fields
    streak = analytics.get("active_streak", 0)
    weekly_hours = analytics.get("weekly_study_hours", 0)
    completed_tasks = analytics.get("completed_tasks", 0)
    total_tasks = analytics.get("total_tasks", 0)
    
    # Workload summary description
    hard_subjects = sum(1 for s in subjects if getattr(s, "difficulty", "") == "Hard")
    workload_summary = (
        f"The student is currently enrolled in {len(subjects)} subjects "
        f"({hard_subjects} Hard difficulty). They have completed {completed_tasks} out of "
        f"{total_tasks} registered tasks."
    )
    
    # Construct LLM prompt
    system_instruction = (
        "You are an expert academic study planner. Your goal is to analyze a student's profile "
        "and generate a highly personalized, realistic weekly study timetable.\n\n"
        "You MUST respond ONLY with a valid JSON object matching the following structure exactly:\n"
        "{\n"
        "  \"schedule\": [\n"
        "    {\n"
        "      \"day\": \"Monday\",\n"
        "      \"subject\": \"Name of Subject\",\n"
        "      \"hours\": 2,\n"
        "      \"reason\": \"Specific reason based on difficulty or upcoming exam\"\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "1. Every day of the week (Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday) can have zero, one, or more sessions.\n"
        "2. Only output subjects that are listed in the user's subjects list.\n"
        "3. Focus study hours more heavily on subjects with upcoming exams (milestones) and harder difficulty.\n"
        "4. Vary the study hours per session strictly based on the subject's difficulty level:\n"
        "   - Hard difficulty subjects MUST be allocated 2.5 to 3.5 hours per session.\n"
        "   - Medium difficulty subjects MUST be allocated 1.5 to 2.0 hours per session.\n"
        "   - Easy difficulty subjects MUST be allocated 1.0 to 1.5 hours per session.\n"
        "5. Respond with ONLY the raw JSON output, without any markdown formatting wrappers or conversational text."
    )
    
    cal_str = "None"
    if calibration:
        cal_str = (
            f"- Daily study quota target: {calibration.get('daily_quota', 6)} hours\n"
            f"- Optimal focus period: {calibration.get('focus_period', 'Morning')}\n"
            f"- Study method: {calibration.get('focus_method', 'Classic Pomodoro')}\n"
            f"- Avoid early mornings: {'Yes' if calibration.get('avoid_early_mornings') else 'No'}\n"
            f"- Prioritize critical subjects: {'Yes' if calibration.get('prioritize_critical') else 'No'}\n"
            f"- Intensive pre-exam review: {'Yes' if calibration.get('intensive_pre_exam') else 'No'}\n"
            f"- Weekend preservation: {'Yes' if calibration.get('weekend_preservation') else 'No'}"
        )

    user_prompt = (
        f"Please generate a study plan for this student:\n\n"
        f"Subjects:\n{subjects_str}\n\n"
        f"Upcoming Exam Milestones:\n{milestones_str}\n\n"
        f"Study Streak: {streak} days\n"
        f"Weekly Study Hours: {weekly_hours} hours\n"
        f"Workload Summary: {workload_summary}\n\n"
        f"Study Preferences & Constraints:\n{cal_str}\n\n"
        f"JSON output:"
    )
    
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    model_name = LLM_MODEL
    if "groq" in LLM_API_URL.lower() and model_name == "llama-3.3-70b":
        model_name = "llama-3.3-70b-versatile"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }
    
    url = f"{LLM_API_URL}/chat/completions"
    
    try:
        logger.debug(f"Sending request to LLM API url: {url}")
        with httpx.Client(timeout=25.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            # Extract content
            choices = result.get("choices", [])
            if not choices:
                raise ValueError("LLM response did not contain any choices.")
                
            content = choices[0].get("message", {}).get("content", "").strip()
            logger.debug(f"Received raw LLM response: {content}")
            
            parsed_data = json.loads(content)
            if not validate_schedule_json(parsed_data):
                raise ValueError("LLM response did not pass schema validation.")
                
            return parsed_data
            
    except Exception as e:
        logger.error(f"Error communicating with LLM API: {e}", exc_info=True)
        raise RuntimeError(f"LLM generation failed: {e}")
