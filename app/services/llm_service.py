import json
import logging
import httpx
import hashlib
import time
from datetime import date, datetime, timedelta
from app.config import LLM_API_KEY, LLM_MODEL, LLM_API_URL

logger = logging.getLogger("llm_service")

def clean_json_response(content: str) -> str:
    """Cleans potential markdown JSON wrappers from LLM response."""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()

def validate_schedule_json(data: dict) -> bool:
    """
    Validates that the returned data is a dict containing a 'schedule' key
    whose value is a list of items matching the required structure.
    Also validates the presence of 'detailed_analysis' and 'quality_scoring' keys.
    """
    if not isinstance(data, dict):
        logger.warning("Validation failed: Root is not a dictionary.")
        return False

    if "schedule" not in data:
        logger.warning("Validation failed: Root key 'schedule' is missing.")
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
        required_keys = ("day", "subject", "hours", "reason", "session_type")
        if not all(k in item for k in required_keys):
            missing = [k for k in required_keys if k not in item]
            logger.warning(f"Validation failed: schedule item at index {idx} is missing keys: {missing}")
            return False
        # Check types
        if not isinstance(item["day"], str) or not isinstance(item["subject"], str) or not isinstance(item["session_type"], str):
            logger.warning(f"Validation failed: 'day', 'subject' or 'session_type' at index {idx} is not a string.")
            return False
        if not isinstance(item["hours"], (int, float)):
            logger.warning(f"Validation failed: 'hours' at index {idx} is not a number.")
            return False
        if not isinstance(item["reason"], str):
            logger.warning(f"Validation failed: 'reason' at index {idx} is not a string.")
            return False
        if "start_time" in item and not isinstance(item["start_time"], str):
            logger.warning(f"Validation failed: 'start_time' at index {idx} is not a string.")
            return False
        if "end_time" in item and not isinstance(item["end_time"], str):
            logger.warning(f"Validation failed: 'end_time' at index {idx} is not a string.")
            return False
            
    # Validate 'detailed_analysis'
    if "detailed_analysis" not in data:
        logger.warning("Validation failed: 'detailed_analysis' key is missing.")
        return False
        
    da = data["detailed_analysis"]
    if not isinstance(da, dict):
        logger.warning("Validation failed: 'detailed_analysis' is not a dictionary.")
        return False
        
    required_da_keys = (
        "focus_title", 
        "focus_description", 
        "focus_blocks", 
        "phases", 
        "pro_tips",
        "subject_allocation_reasons",
        "time_slot_reasons",
        "milestone_reasons",
        "preference_reasons"
    )
    if not all(k in da for k in required_da_keys):
        missing = [k for k in required_da_keys if k not in da]
        logger.warning(f"Validation failed: 'detailed_analysis' is missing keys: {missing}")
        return False
        
    if not isinstance(da["focus_blocks"], list) or not isinstance(da["phases"], list) or not isinstance(da["pro_tips"], list):
        logger.warning("Validation failed: 'focus_blocks', 'phases', or 'pro_tips' inside 'detailed_analysis' is not a list.")
        return False

    if not isinstance(da["subject_allocation_reasons"], dict):
        logger.warning("Validation failed: 'subject_allocation_reasons' is not a dictionary.")
        return False
        
    # Validate 'quality_scoring'
    if "quality_scoring" not in data:
        logger.warning("Validation failed: 'quality_scoring' key is missing.")
        return False
        
    qs = data["quality_scoring"]
    if not isinstance(qs, dict):
        logger.warning("Validation failed: 'quality_scoring' is not a dictionary.")
        return False
        
    required_qs_keys = ("balance_score", "burnout_risk", "exam_readiness_score")
    if not all(k in qs for k in required_qs_keys):
        missing = [k for k in required_qs_keys if k not in qs]
        logger.warning(f"Validation failed: 'quality_scoring' is missing keys: {missing}")
        return False
        
    return True

def validate_candidates_json(data: dict) -> bool:
    """Validates structure of candidates JSON output."""
    if not isinstance(data, dict):
        logger.warning("Candidates validation failed: Root is not a dictionary.")
        return False
    if "candidates" not in data:
        logger.warning("Candidates validation failed: 'candidates' key is missing.")
        return False
    candidates = data["candidates"]
    if not isinstance(candidates, list) or len(candidates) == 0:
        logger.warning("Candidates validation failed: 'candidates' is empty or not a list.")
        return False
    for idx, c in enumerate(candidates):
        if not isinstance(c, dict) or "schedule" not in c or "candidate_id" not in c:
            logger.warning(f"Candidates validation failed: candidate at index {idx} is invalid.")
            return False
        schedule = c["schedule"]
        if not isinstance(schedule, list):
            logger.warning(f"Candidates validation failed: candidate {idx} schedule is not a list.")
            return False
        for s_idx, item in enumerate(schedule):
            required = ("day", "subject", "hours", "reason", "session_type")
            if not all(k in item for k in required):
                logger.warning(f"Candidates validation failed: session {s_idx} in candidate {idx} missing keys.")
                return False
    return True

def call_llm_api(system_instruction: str, user_prompt: str) -> dict:
    """Wrapper to make standard POST request to the LLM API and parse JSON response with 429 retry backoff."""
    if not LLM_API_KEY:
        logger.error("LLM_API_KEY is not configured.")
        raise ValueError("LLM_API_KEY is not configured.")
        
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
    logger.debug(f"Sending request to LLM API: {url}")
    
    max_retries = 5
    backoff_factor = 2.0
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=25.0) as client:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code == 429:
                    sleep_time = (backoff_factor ** attempt) + 1.0
                    logger.warning(f"Rate limited (429) on attempt {attempt + 1}. Retrying in {sleep_time:.1f}s...")
                    time.sleep(sleep_time)
                    continue
                response.raise_for_status()
                result = response.json()
                choices = result.get("choices", [])
                if not choices:
                    raise ValueError("LLM response did not contain any choices.")
                content = choices[0].get("message", {}).get("content", "").strip()
                logger.debug(f"Received raw LLM response: {content}")
                
                cleaned = clean_json_response(content)
                return json.loads(cleaned)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                sleep_time = (backoff_factor ** attempt) + 1.0
                logger.warning(f"Rate limited (429) via HTTPStatusError on attempt {attempt + 1}. Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)
                continue
            logger.error(f"HTTP error occurred in call_llm_api: {e}")
            raise e
        except Exception as e:
            logger.error(f"Error occurred in call_llm_api on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise e
            time.sleep(1.0)
    raise RuntimeError("Max retries exceeded in call_llm_api.")

def calculate_schedule_metrics(schedule_events: list, milestones: list, subjects: list, db=None) -> dict:
    """
    Calculates Balance Score, Burnout Risk, and Exam Readiness based on the final generated timetable,
    milestones, and user performance statistics.
    Logs all inputs and intermediate calculations.
    """
    logger.info("Starting quality metrics calculation.")
    
    # 1. BALANCE SCORE CALCULATION
    balance_score = 0
    subject_balance = 0
    daily_balance = 0
    
    num_subjects = len(subjects)
    if num_subjects == 0:
        balance_score = 100
        logger.info("Balance Score: 100 (0 subjects registered)")
    else:
        # Calculate scheduled hours per subject
        subject_hours = {s.name.lower().strip(): 0.0 for s in subjects}
        for event in schedule_events:
            sub_name = event.get("subject", "").lower().strip()
            hours = float(event.get("hours", 0.0))
            # Find closest matching subject name
            matched = False
            for s_name in subject_hours.keys():
                if s_name in sub_name or sub_name in s_name:
                    subject_hours[s_name] += hours
                    matched = True
                    break
            if not matched and sub_name:
                subject_hours[sub_name] = subject_hours.get(sub_name, 0.0) + hours

        # Subject Coverage
        allocated_subjects = sum(1 for h in subject_hours.values() if h > 0)
        subject_coverage = allocated_subjects / num_subjects
        
        # Subject Distribution (Coefficient of Variation)
        allocated_hours = [h for h in subject_hours.values() if h > 0]
        if len(allocated_hours) == 0:
            subject_distribution = 0.0
        elif len(allocated_hours) == 1:
            subject_distribution = 1.0 if num_subjects == 1 else 0.5
        else:
            mean_h = sum(allocated_hours) / len(allocated_hours)
            variance = sum((x - mean_h) ** 2 for x in allocated_hours) / len(allocated_hours)
            std_h = variance ** 0.5
            cv_h = std_h / mean_h if mean_h > 0 else 0.0
            subject_distribution = max(0.0, 1.0 - 0.4 * cv_h)
            
        subject_balance = subject_coverage * subject_distribution * 100
        
        # Daily workload balance
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        daily_hours = {d: 0.0 for d in days}
        for event in schedule_events:
            day = event.get("day", "")
            hours = float(event.get("hours", 0.0))
            if day in daily_hours:
                daily_hours[day] += hours
                
        total_weekly_hours = sum(daily_hours.values())
        if total_weekly_hours == 0:
            daily_balance = 100
        else:
            mean_d = total_weekly_hours / 7.0
            variance_d = sum((x - mean_d) ** 2 for x in daily_hours.values()) / 7.0
            std_d = variance_d ** 0.5
            cv_d = std_d / mean_d if mean_d > 0 else 0.0
            daily_balance = max(0.0, 1.0 - 0.3 * cv_d) * 100
            
        balance_score = int(0.5 * subject_balance + 0.5 * daily_balance)
        balance_score = max(0, min(100, balance_score))
        
        # Debug Logging for Balance Score
        logger.info(
            f"Balance Score Inputs & Calculation:\n"
            f"- Subjects list: {[s.name for s in subjects]}\n"
            f"- Hours per subject: {subject_hours}\n"
            f"- Total subjects: {num_subjects}, Allocated: {allocated_subjects}\n"
            f"- Subject Coverage: {subject_coverage:.2f}, Subject Distribution: {subject_distribution:.2f}\n"
            f"- Subject Balance component: {subject_balance:.2f}\n"
            f"- Daily hours: {daily_hours}\n"
            f"- Total weekly hours: {total_weekly_hours:.2f}\n"
            f"- Daily Mean: {mean_d:.2f}, StdDev: {std_d:.2f}, CV: {cv_d:.2f}\n"
            f"- Daily Balance component: {daily_balance:.2f}\n"
            f"- Final Calculated Balance Score: {balance_score}%"
        )

    # 2. BURNOUT RISK CALCULATION
    # Get daily hours and blocks
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    daily_hours = {d: 0.0 for d in days}
    daily_blocks = {d: 0 for d in days}
    for event in schedule_events:
        day = event.get("day", "")
        hours = float(event.get("hours", 0.0))
        if day in daily_hours:
            daily_hours[day] += hours
            daily_blocks[day] += 1

    # Daily study hours burnout contribution (expected scaling)
    # 6h/day avg -> 24%
    # 8h/day avg -> 50%
    # 10h/day avg -> 75%
    # 12h/day avg -> 100%
    avg_daily_hours = sum(daily_hours.values()) / 7.0
    if avg_daily_hours <= 6.0:
        risk_hours = avg_daily_hours * 4.0
    elif avg_daily_hours <= 8.0:
        risk_hours = 24.0 + (avg_daily_hours - 6.0) * 13.0
    elif avg_daily_hours <= 10.0:
        risk_hours = 50.0 + (avg_daily_hours - 8.0) * 12.5
    else:
        risk_hours = 75.0 + (avg_daily_hours - 10.0) * 12.5
    risk_hours = max(0.0, min(100.0, risk_hours))

    # Number of study blocks contribution
    # Rule 5: Too few breaks increases risk, study sessions being distributed decreases risk
    avg_blocks = sum(daily_blocks.values()) / 7.0
    if avg_daily_hours > 3.0 and avg_blocks < 2.0:
        risk_blocks = 75.0  # too few breaks
    else:
        # Having more blocks (well-distributed sessions) reduces risk
        risk_blocks = max(10.0, 50.0 - (avg_blocks - 1.5) * 15.0)
    risk_blocks = min(100.0, max(0.0, risk_blocks))

    # Continuous study duration contribution
    max_block_duration = 0.0
    for event in schedule_events:
        hours = float(event.get("hours", 0.0))
        if hours > max_block_duration:
            max_block_duration = hours
            
    risk_block_duration = 10.0
    if max_block_duration > 3.0:
        risk_block_duration = 100.0
    elif max_block_duration > 2.0:
        risk_block_duration = 80.0
    elif max_block_duration > 1.5:
        risk_block_duration = 50.0
    elif max_block_duration > 1.0:
        risk_block_duration = 30.0

    # Recovery periods contribution
    recovery_days = sum(1 for h in daily_hours.values() if h < 2.0)
    risk_recovery = 0.0
    if recovery_days >= 3:
        risk_recovery = 10.0
    elif recovery_days == 2:
        risk_recovery = 30.0
    elif recovery_days == 1:
        risk_recovery = 65.0
    elif recovery_days == 0:
        risk_recovery = 100.0

    # Weekend load contribution
    weekend_load = daily_hours["Saturday"] + daily_hours["Sunday"]
    risk_weekend = 10.0
    if weekend_load > 6.0:
        risk_weekend = 85.0
    elif weekend_load > 4.0:
        risk_weekend = 60.0
    elif weekend_load > 2.0:
        risk_weekend = 40.0

    # Consecutive intensive days contribution (intensive: >= 6.0 hours)
    max_consecutive = 0
    current_consecutive = 0
    for day in days:
        if daily_hours[day] >= 6.0:
            current_consecutive += 1
            if current_consecutive > max_consecutive:
                max_consecutive = current_consecutive
        else:
            current_consecutive = 0
            
    risk_intensive = 10.0
    if max_consecutive == 3:
        risk_intensive = 40.0
    elif max_consecutive == 4:
        risk_intensive = 65.0
    elif max_consecutive == 5:
        risk_intensive = 80.0
    elif max_consecutive >= 6:
        risk_intensive = 100.0

    # Sleep window contribution (sessions running past 11:00 PM or starting before 5:00 AM)
    late_sessions = 0
    for event in schedule_events:
        end_time_str = event.get("end_time", "")
        start_time_str = event.get("start_time", "")
        try:
            h_end = int(end_time_str.split(":")[0])
            h_start = int(start_time_str.split(":")[0])
            if h_end >= 23 or h_end < 5 or h_start < 5:
                late_sessions += 1
        except Exception as e:
            logger.debug(f"Failed to parse sleep window times ({start_time_str} - {end_time_str}): {e}")
            
    risk_sleep = 10.0
    if late_sessions in (1, 2):
        risk_sleep = 45.0
    elif late_sessions in (3, 4):
        risk_sleep = 75.0
    elif late_sessions >= 5:
        risk_sleep = 100.0

    # Gap and cognitive load/stacking analysis for weekdays
    def time_to_min(t_str: str) -> int:
        t_str = t_str.strip().lower()
        is_pm = False
        if "pm" in t_str:
            is_pm = True
            t_str = t_str.replace("pm", "").strip()
        elif "am" in t_str:
            t_str = t_str.replace("am", "").strip()
            
        parts = t_str.split(":")
        if len(parts) == 2:
            h = int(parts[0])
            m = int(parts[1])
        elif len(parts) == 1:
            h = int(parts[0])
            m = 0
        else:
            h = 12
            m = 0
            
        if is_pm and h < 12:
            h += 12
        if not is_pm and h == 12:
            h = 0
        return h * 60 + m

    # Additional modifiers for breaks/gaps and stacking
    gap_penalty = 0
    stacked_hard_penalty = 0
    subject_difficulty_map = {s.name.lower().strip(): s.difficulty for s in subjects}

    for day in days:
        day_events = [e for e in schedule_events if e.get("day") == day]
        if len(day_events) >= 2:
            def get_event_start_min(e):
                st = e.get("start_time")
                if not st:
                    return 0
                try:
                    return time_to_min(st)
                except Exception as e:
                    logger.debug(f"Failed to parse event start time '{st}' into minutes: {e}")
                    return 0
            day_events.sort(key=get_event_start_min)
            for i in range(len(day_events) - 1):
                e1 = day_events[i]
                e2 = day_events[i+1]
                try:
                    end_e1 = time_to_min(e1.get("end_time", "00:00"))
                    start_e2 = time_to_min(e2.get("start_time", "00:00"))
                    gap = start_e2 - end_e1
                    if gap < 0:
                        gap += 24 * 60
                    
                    # Too few breaks / gap < 60 minutes
                    if gap < 60:
                        gap_penalty += 15
                    # Healthy break decreases risk
                    elif 60 <= gap <= 180:
                        gap_penalty -= 5
                        
                    # Stacking check for Hard subjects
                    sub1_name = e1.get("subject", "").lower().strip()
                    sub2_name = e2.get("subject", "").lower().strip()
                    
                    sub1_diff = "Medium"
                    for name, diff in subject_difficulty_map.items():
                        if name in sub1_name or sub1_name in name:
                            sub1_diff = diff
                            break
                    sub2_diff = "Medium"
                    for name, diff in subject_difficulty_map.items():
                        if name in sub2_name or sub2_name in name:
                            sub2_diff = diff
                            break
                            
                    if sub1_diff == "Hard" and sub2_diff == "Hard" and gap < 60:
                        stacked_hard_penalty += 20
                except Exception as e:
                    logger.debug(f"Failed to analyze consecutive events overlap or subject difficulty: {e}")

    # Balance score modifier
    balance_modifier = 0
    if balance_score >= 80:
        balance_modifier = -10
    elif balance_score < 50:
        balance_modifier = 15

    # Base weighted burnout risk
    base_burnout = (
        0.45 * risk_hours +
        0.10 * risk_blocks +
        0.10 * risk_block_duration +
        0.10 * risk_recovery +
        0.08 * risk_weekend +
        0.08 * risk_intensive +
        0.09 * risk_sleep
    )
    
    # Apply penalties & rewards
    burnout_risk = int(base_burnout + gap_penalty + stacked_hard_penalty + balance_modifier)
    burnout_risk = max(0, min(100, burnout_risk))

    # Debug Logging for Burnout Risk
    logger.info(
        f"Burnout Risk Inputs & Calculation:\n"
        f"- Daily hours: {daily_hours}\n"
        f"- Daily blocks: {daily_blocks}\n"
        f"- Average study hours: {avg_daily_hours:.2f} -> Hours Risk: {risk_hours:.2f}%\n"
        f"- Average blocks: {avg_blocks:.2f} -> Blocks Risk: {risk_blocks:.2f}%\n"
        f"- Max block duration: {max_block_duration:.2f}h -> Continuous Risk: {risk_block_duration:.2f}%\n"
        f"- Recovery days count (<2h): {recovery_days} -> Recovery Risk: {risk_recovery:.2f}%\n"
        f"- Weekend hours load: {weekend_load:.2f}h -> Weekend Risk: {risk_weekend:.2f}%\n"
        f"- Max consecutive intensive days: {max_consecutive} -> Intensive Risk: {risk_intensive:.2f}%\n"
        f"- Late sessions (ending >=11PM): {late_sessions} -> Sleep Risk: {risk_sleep:.2f}%\n"
        f"- Final Calculated Burnout Risk: {burnout_risk}%"
    )

    # 3. EXAM READINESS SCORE CALCULATION
    exam_readiness_score = 0
    if not milestones:
        exam_readiness_score = 0
        logger.info("Exam Readiness Score: 0% (no exam milestones found)")
    else:
        readiness_scores = []
        current_date = date(2026, 6, 14)  # Current local time date context
        
        for m in milestones:
            sub_name_clean = m.subject_name.lower().strip()
            
            subj_obj = None
            for s in subjects:
                if s.name.lower().strip() == sub_name_clean:
                    subj_obj = s
                    break
            if not subj_obj:
                for s in subjects:
                    if s.name.lower().strip() in sub_name_clean or sub_name_clean in s.name.lower().strip():
                        subj_obj = s
                        break
            
            difficulty = subj_obj.difficulty if subj_obj else "Medium"
            if not difficulty:
                difficulty = "Medium"
                
            # Hours allocated before exam for this subject
            h_allocated = 0.0
            for event in schedule_events:
                event_sub = event.get("subject", "").lower().strip()
                if event_sub == sub_name_clean or event_sub in sub_name_clean or sub_name_clean in event_sub:
                    h_allocated += float(event.get("hours", 0.0))
            
            # Target hours needed based on difficulty
            h_target = 6.0
            if difficulty == "Hard":
                h_target = 10.0
            elif difficulty == "Easy":
                h_target = 4.0
                
            hours_score = min(100.0, (h_allocated / h_target) * 100.0)
            
            # Proximity in days
            days_prox = 10 # Default fallback
            try:
                exam_date_obj = m.exam_date
                if isinstance(exam_date_obj, str):
                    exam_date_obj = datetime.strptime(exam_date_obj.split()[0], "%Y-%m-%d").date()
                days_prox = (exam_date_obj - current_date).days
            except Exception:
                pass
            
            if days_prox < 0:
                days_prox = 0
                
            proximity_modifier = 1.0
            if days_prox <= 1:
                proximity_modifier = 0.5
            elif days_prox <= 3:
                proximity_modifier = 0.7
            elif days_prox <= 7:
                proximity_modifier = 0.9
                
            # Performance metrics (database-backed milestone completion percentage)
            completion = m.completion_percentage if m.completion_percentage is not None else 0
            perf_score = float(completion)
            
            # Completed study sessions count
            sessions_count = 0
            if db is not None and subj_obj is not None:
                try:
                    from app.models import StudySession
                    sessions_count = db.query(StudySession).filter(
                        StudySession.user_id == m.user_id,
                        StudySession.subject_id == subj_obj.id
                    ).count()
                except Exception as db_err:
                    logger.error(f"Error querying study sessions count for readiness: {db_err}")
            
            session_factor = min(100.0, sessions_count * 20.0)
            
            # Weighted calculation of milestone readiness
            m_readiness = 0.3 * hours_score + 0.4 * perf_score + 0.3 * session_factor
            m_readiness = m_readiness * proximity_modifier
            m_readiness = max(0.0, min(100.0, m_readiness))
            readiness_scores.append(m_readiness)
            
            logger.info(
                f"Milestone Exam Readiness calculation details for {m.subject_name}:\n"
                f"- Exam Date: {m.exam_date} (Proximity: {days_prox} days, Modifier: {proximity_modifier:.2f})\n"
                f"- Difficulty: {difficulty} (Target: {h_target}h, Allocated: {h_allocated}h -> Hours Score: {hours_score:.2f}%)\n"
                f"- Performance: Completion={completion}% -> Perf Score: {perf_score:.2f}%\n"
                f"- Completed sessions count: {sessions_count} -> Session Factor: {session_factor:.2f}%\n"
                f"- Calculated Milestone Readiness: {m_readiness:.2f}%"
            )
            
        exam_readiness_score = int(sum(readiness_scores) / len(readiness_scores))
        exam_readiness_score = max(0, min(100, exam_readiness_score))
        logger.info(f"Final Combined Calculated Exam Readiness Score: {exam_readiness_score}%")
        
    return {
        "balance_score": balance_score,
        "burnout_risk": burnout_risk,
        "exam_readiness_score": exam_readiness_score
    }

def calculate_dynamic_schedule_label(schedule_events: list) -> str:
    """
    Dynamically generates the focus schedule label based on the actual time allocation of events.
    """
    total_hours = sum(float(event.get("hours", 0.0)) for event in schedule_events)
    
    morning_hours = 0.0
    afternoon_hours = 0.0
    night_hours = 0.0
    
    for event in schedule_events:
        start_str = event.get("start_time", "09:00")
        hours = float(event.get("hours", 0.0))
        try:
            h = int(start_str.split(":")[0])
            if 5 <= h < 12:
                morning_hours += hours
            elif 12 <= h < 17:
                afternoon_hours += hours
            else:
                night_hours += hours
        except Exception:
            start_str_lower = start_str.lower()
            if "am" in start_str_lower:
                morning_hours += hours
            elif "pm" in start_str_lower:
                h = int(start_str_lower.split(":")[0].replace("pm", "").strip())
                if h < 5 or h == 12:
                    afternoon_hours += hours
                else:
                    night_hours += hours
            else:
                night_hours += hours

    if total_hours == 0:
        return "Standard Study Schedule"
        
    logger.info(f"Dynamic Label Classification - Total: {total_hours}h, Morning: {morning_hours}h, Afternoon: {afternoon_hours}h, Night/Evening: {night_hours}h")
    
    max_hours = max(morning_hours, afternoon_hours, night_hours)
    
    sorted_hours = sorted([morning_hours, afternoon_hours, night_hours], reverse=True)
    if sorted_hours[0] - sorted_hours[1] < (total_hours * 0.2):
        return f"Balanced Rhythm Focus Schedule ({total_hours:.1f} Hours/Week)"
        
    if max_hours == morning_hours:
        return f"Morning Focus Schedule ({total_hours:.1f} Hours/Week)"
    elif max_hours == afternoon_hours:
        return f"Afternoon Focus Schedule ({total_hours:.1f} Hours/Week)"
    else:
        return f"Night Focus Schedule ({total_hours:.1f} Hours/Week)"

def verify_consistency(schedule_events: list, detailed_analysis: dict, milestones: list, subjects: list) -> bool:
    """
    Performs consistency validation to ensure study map, phases, blocks and timetables align.
    """
    logger.info("Running Consistency Validation Checks...")
    
    scheduled_subjects = {event.get("subject", "").lower().strip() for event in schedule_events}
    
    # 1. Study Map subjects exist in timetable
    reasons_dict = detailed_analysis.get("subject_allocation_reasons", {})
    for sub in reasons_dict.keys():
        sub_clean = sub.lower().strip()
        matched = False
        for s_sub in scheduled_subjects:
            if s_sub == sub_clean or s_sub in sub_clean or sub_clean in s_sub:
                matched = True
                break
        if not matched:
            logger.warning(f"Consistency Validation Failed: Subject '{sub}' in Study Map allocations does not exist in weekly timetable subjects {scheduled_subjects}")
            return False

    # 2. Phase subjects exist in milestones
    milestone_subjects = {m.subject_name.lower().strip() for m in milestones}
    phases = detailed_analysis.get("phases", [])
    for phase in phases:
        title = phase.get("title", "").lower()
        description = phase.get("description", "").lower()
        allocations = phase.get("allocations", [])
        
        matched_milestone = False
        for ms in milestone_subjects:
            if ms in title or ms in description or any(ms in str(alloc).lower() for alloc in allocations):
                matched_milestone = True
                break
        if not matched_milestone and milestone_subjects:
            logger.warning(f"Consistency Validation Failed: Phase '{phase.get('title')}' does not relate to any registered exam milestones {milestone_subjects}")
            return False

    # Helper function for parsing time to minutes
    def time_to_min(t_str: str) -> int:
        t_str = t_str.strip().lower()
        is_pm = False
        if "pm" in t_str:
            is_pm = True
            t_str = t_str.replace("pm", "").strip()
        elif "am" in t_str:
            t_str = t_str.replace("am", "").strip()
            
        parts = t_str.split(":")
        if len(parts) == 2:
            h = int(parts[0])
            m = int(parts[1])
        else:
            h = int(parts[0])
            m = 0
            
        if is_pm and h < 12:
            h += 12
        if not is_pm and h == 12:
            h = 0
        return h * 60 + m

    # 3. Block timings exist in timetable
    blocks = detailed_analysis.get("focus_blocks", [])
    for b in blocks:
        time_range = b.get("time", "")
        if not time_range:
            continue
        sep = "–" if "–" in time_range else "-"
        parts = time_range.split(sep)
        if len(parts) != 2:
            logger.warning(f"Consistency Validation Warning: block time range format invalid: {time_range}")
            continue
            
        try:
            start_block = time_to_min(parts[0])
            end_block = time_to_min(parts[1])
            if end_block < start_block:
                end_block += 24 * 60
        except Exception as te:
            logger.warning(f"Consistency Validation Warning: error parsing block time '{time_range}': {te}")
            continue
            
        overlap_found = False
        for event in schedule_events:
            event_start_str = event.get("start_time", "")
            event_end_str = event.get("end_time", "")
            if not event_start_str or not event_end_str:
                continue
                
            try:
                start_ev = time_to_min(event_start_str)
                end_ev = time_to_min(event_end_str)
                if end_ev < start_ev:
                    end_ev += 24 * 60
                
                if max(start_block, start_ev) < min(end_block, end_ev):
                    overlap_found = True
                    break
            except Exception:
                continue
                
        if not overlap_found and schedule_events:
            logger.warning(f"Consistency Validation Failed: Block time '{time_range}' has no overlapping scheduled sessions in the timetable.")
            return False

    def parse_mil_date(m):
        try:
            exam_date_obj = m.exam_date
            if isinstance(exam_date_obj, str):
                exam_date_obj = datetime.strptime(exam_date_obj.split()[0], "%Y-%m-%d").date()
            return exam_date_obj
        except Exception:
            return date.max

    milestones_sorted = sorted(milestones, key=parse_mil_date)
    milestone_subject_order = {m.subject_name.lower().strip(): idx for idx, m in enumerate(milestones_sorted)}
    last_idx = -1
    for phase in phases:
        phase_subj_indices = []
        for sub_name, order_idx in milestone_subject_order.items():
            if sub_name in phase.get("title", "").lower() or sub_name in phase.get("description", "").lower():
                phase_subj_indices.append(order_idx)
        if phase_subj_indices:
            min_idx_in_phase = min(phase_subj_indices)
            if min_idx_in_phase < last_idx:
                logger.warning(f"Consistency Validation Failed: Phase order is not chronological. Phase {phase.get('title')} is out of order.")
                return False
            last_idx = min_idx_in_phase

    logger.info("Consistency Validation Successful!")
    return True

def enforce_weekend_preservation(schedule_events, milestones, daily_quota):
    # Filter weekday events
    weekday_events = [e for e in schedule_events if e.get("day") in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]]
    
    # Filter weekend events
    weekend_events = [e for e in schedule_events if e.get("day") in ["Saturday", "Sunday"]]
    
    # Check if any milestone exam is less than 5 days away
    exam_soon = False
    today = date.today()
    upcoming_exam_subject = None
    for m in milestones:
        try:
            exam_date = m.exam_date
            if isinstance(exam_date, str):
                exam_date = datetime.strptime(exam_date.split()[0], "%Y-%m-%d").date()
            if exam_date:
                days_left = (exam_date - today).days
                if 0 <= days_left < 5:
                    exam_soon = True
                    upcoming_exam_subject = m.subject_name
                    break
        except Exception:
            pass
            
    retained_weekend_study = None
    redistribute_list = []
    
    for e in weekend_events:
        is_study = e.get("session_type") not in ["Rest", "Recovery", "Mindfulness", "Break", "Buffer Time"]
        if is_study:
            if exam_soon and not retained_weekend_study and e.get("subject") == upcoming_exam_subject:
                # Keep this one lightweight study session, max 1.5 hours
                retained_weekend_study = e
                retained_weekend_study["session_type"] = "Revision"
                retained_weekend_study["hours"] = 1.5
                retained_weekend_study["start_time"] = "13:00"
                retained_weekend_study["end_time"] = "14:30"
                retained_weekend_study["reason"] = f"Lightweight exam preparation review for {retained_weekend_study.get('subject')}."
            else:
                redistribute_list.append(e)
                
    # Redistribute the other weekend study hours to weekdays
    if redistribute_list:
        weekday_hours = {d: 0.0 for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]}
        for we in weekday_events:
            weekday_hours[we.get("day")] = weekday_hours.get(we.get("day"), 0.0) + float(we.get("hours", 0.0))
            
        for e in redistribute_list:
            target_day = min(weekday_hours, key=weekday_hours.get)
            
            # Try to extend existing session of same subject on that day
            found_same_subject = False
            for we in weekday_events:
                if we.get("day") == target_day and we.get("subject") == e.get("subject"):
                    we["hours"] = float(we.get("hours", 0.0)) + float(e.get("hours", 0.0))
                    try:
                        h, m = map(int, we["start_time"].split(":"))
                        total_m = h * 60 + m + int(we["hours"] * 60)
                        new_h = (total_m // 60) % 24
                        new_m = total_m % 60
                        we["end_time"] = f"{new_h:02d}:{new_m:02d}"
                    except Exception:
                        pass
                    found_same_subject = True
                    break
                    
            if not found_same_subject:
                start_time = "14:00"
                max_end_minutes = 0
                for we in weekday_events:
                    if we.get("day") == target_day:
                        try:
                            h, m = map(int, we["end_time"].split(":"))
                            end_min = h * 60 + m
                            if end_min > max_end_minutes:
                                max_end_minutes = end_min
                        except Exception:
                            pass
                if max_end_minutes > 0:
                    start_min = max_end_minutes + 120
                    if start_min >= 22 * 60:
                        start_min = 9 * 60
                    new_h = (start_min // 60) % 24
                    new_m = start_min % 60
                    start_time = f"{new_h:02d}:{new_m:02d}"
                    
                try:
                    h, m = map(int, start_time.split(":"))
                    end_min = h * 60 + m + int(float(e.get("hours", 0.0)) * 60)
                    new_h = (end_min // 60) % 24
                    new_m = end_min % 60
                    end_time = f"{new_h:02d}:{new_m:02d}"
                except Exception:
                    end_time = start_time
                    
                new_event = {
                    "day": target_day,
                    "subject": e.get("subject"),
                    "hours": float(e.get("hours", 0.0)),
                    "start_time": start_time,
                    "end_time": end_time,
                    "session_type": e.get("session_type"),
                    "reason": f"Shifted from weekend to preserve rest: {e.get('reason')}"
                }
                weekday_events.append(new_event)
                
            weekday_hours[target_day] += float(e.get("hours", 0.0))
            
    # Reassemble final schedule
    final_events = []
    final_events.extend(weekday_events)
    
    if retained_weekend_study:
        final_events.append(retained_weekend_study)
        
    # Append the Rest/Recovery/Mindfulness blocks to Saturday and Sunday
    default_sat_blocks = [
        {
            "day": "Saturday",
            "subject": "Rest & Recharge",
            "hours": 2.0,
            "start_time": "10:00",
            "end_time": "12:00",
            "session_type": "Recovery",
            "reason": "Protected recovery slot to prevent academic burnout."
        },
        {
            "day": "Saturday",
            "subject": "Mindfulness",
            "hours": 1.5,
            "start_time": "15:00",
            "end_time": "16:30",
            "session_type": "Mindfulness",
            "reason": "Mental decompression and stress management session."
        }
    ]
    default_sun_blocks = [
        {
            "day": "Sunday",
            "subject": "Rest & Recharge",
            "hours": 2.0,
            "start_time": "10:00",
            "end_time": "12:00",
            "session_type": "Rest",
            "reason": "Complete downtime to build cognitive reserves for the week ahead."
        },
        {
            "day": "Sunday",
            "subject": "Mindfulness",
            "hours": 1.5,
            "start_time": "15:00",
            "end_time": "16:30",
            "session_type": "Recovery",
            "reason": "Restorative relaxation block to boost mental clarity."
        }
    ]
    
    final_events.extend(default_sat_blocks)
    final_events.extend(default_sun_blocks)
    
    return final_events

def generate_ai_schedule(
    user_id: int,
    subjects: list,
    milestones: list,
    analytics: dict,
    calibration: dict = None,
    db = None
) -> dict:
    """
    Generates a personalized weekly study timetable and detailed strategic analysis in a single LLM call.
    Uses file-based caching to prevent redundant API calls.
    """
    
    logger.info(f"Generating AI study plan for user {user_id} using model {LLM_MODEL}")
    
    # Standardize calibration defaults
    if not calibration:
        calibration = {}
    calibration_defaults = {
        "daily_quota": 6,
        "focus_period": "Morning",
        "focus_method": "Classic Pomodoro",
        "avoid_early_mornings": False,
        "prioritize_critical": True,
        "intensive_pre_exam": True,
        "weekend_preservation": False,
        "force_refresh": False
    }
    for k, v in calibration_defaults.items():
        if k not in calibration or calibration[k] is None:
            calibration[k] = v
            
    class CalibrationDict(dict):
        @property
        def weekend_preservation(self):
            return self.get("weekend_preservation")
            
    calibration = CalibrationDict(calibration)
    
    logger.info(
        f"Weekend Preservation: {calibration.weekend_preservation}"
    )
    
    weekend_preservation = calibration.weekend_preservation
    logger.info(
        f"Applying weekend preservation: {weekend_preservation}"
    )
            
    force_refresh = calibration.get("force_refresh", False)
    
    # ------------------------------------------
    # Cache Check
    # ------------------------------------------
    from app.database import DB_DIR
    import os
    
    # Generate unique cache path based on inputs
    sub_sig = sorted([(s.name.lower().strip(), s.difficulty) for s in subjects])
    mil_sig = sorted([(m.subject_name.lower().strip(), m.exam_date) for m in milestones])
    cal_sig = sorted([(str(k), str(v)) for k, v in calibration.items() if k != "force_refresh"])
    
    cache_inputs = {
        "user_id": user_id,
        "subjects": sub_sig,
        "milestones": mil_sig,
        "calibration": cal_sig
    }
    serialized = json.dumps(cache_inputs, sort_keys=True)
    cache_hash = hashlib.md5(serialized.encode("utf-8")).hexdigest()
    cache_path = DB_DIR / f"schedule_cache_{user_id}_{cache_hash}.json"
    
    if not force_refresh and cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            logger.info(f"Cache hit for user {user_id}. Returning cached schedule. Total LLM calls: 0")
            cached_data["is_cached"] = True
            cached_data["llm_calls_count"] = 0
            return cached_data
        except Exception as cache_err:
            logger.error(f"Failed to read schedule cache: {cache_err}")
            
    # Compile subjects list details
    subject_details = []
    for s in subjects:
        subject_details.append(
            f"- {s.name} (Difficulty: {s.difficulty or 'Medium'})"
        )
    subjects_str = "\n".join(subject_details) if subject_details else "None"
    
    def parse_mil_date(m):
        try:
            exam_date_obj = m.exam_date
            if isinstance(exam_date_obj, str):
                exam_date_obj = datetime.strptime(exam_date_obj.split()[0], "%Y-%m-%d").date()
            return exam_date_obj
        except Exception:
            return date.max

    milestones_sorted = sorted(milestones, key=parse_mil_date)
    milestones_chronology_list = [
        f"- {m.subject_name} (Exam Date: {m.exam_date})"
        for m in milestones_sorted
    ]
    milestones_chronology_str = "\n".join(milestones_chronology_list) if milestones_chronology_list else "None"
    
    milestone_details = []
    for m in milestones_sorted:
        milestone_details.append(f"- Exam for {m.subject_name} on {m.exam_date}")
    milestones_str = "\n".join(milestone_details) if milestone_details else "None"
    
    # Extract analytics fields
    streak = analytics.get("active_streak", 0)
    weekly_hours = analytics.get("weekly_study_hours", 0)
    
    current_date_str = date.today().strftime("%B %d, %Y")
    
    # Fatigue model calculations
    fatigue_level = "Low"
    recovery_recommendation = "None"
    if weekly_hours > 25 or streak > 5:
        fatigue_level = "High"
        recovery_recommendation = "High fatigue detected. Reduce daily study hours by 30%, schedule revision sessions, and insert recovery blocks."
    elif weekly_hours > 15 or streak > 3:
        fatigue_level = "Medium"
        recovery_recommendation = "Moderate fatigue detected. Reduce daily study hours by 15% and insert recovery blocks."
        
    fatigue_str = (
        f"- Fatigue Level: {fatigue_level}\n"
        f"- Streak: {streak} days\n"
        f"- Weekly study: {weekly_hours} hours\n"
        f"- Recovery: {recovery_recommendation}"
    )
    
    cal_str = (
        f"- Daily study quota target: {calibration.get('daily_quota', 6)} hours\n"
        f"- Optimal focus period: {calibration.get('focus_period', 'Morning')}\n"
        f"- Study method: {calibration.get('focus_method', 'Classic Pomodoro')}\n"
        f"- Avoid early mornings: {'Yes' if calibration.get('avoid_early_mornings') else 'No'}\n"
        f"- Prioritize critical subjects: {'Yes' if calibration.get('prioritize_critical') else 'No'}\n"
        f"- Intensive pre-exam review: {'Yes' if calibration.get('intensive_pre_exam') else 'No'}\n"
        f"- Weekend preservation: {'Yes' if calibration.get('weekend_preservation') else 'No'}"
    )

    system_instruction_1 = (
        "You are an expert academic study planner, scheduling engine, and advisor. Your goal is to analyze a student's profile "
        "and generate a single, highly realistic, balanced, and sustainable weekly study schedule along with a detailed strategic analysis.\n\n"
        "You MUST respond ONLY with a valid JSON object matching the following structure exactly:\n"
        "{\n"
        "  \"schedule\": [\n"
        "    {\n"
        "      \"day\": \"Monday\",\n"
        "      \"subject\": \"Name of Subject\",\n"
        "      \"hours\": 1.5,\n"
        "      \"start_time\": \"15:00\",\n"
        "      \"end_time\": \"16:30\",\n"
        "      \"session_type\": \"Deep Focus\",\n"
        "      \"reason\": \"Reason including Pomodoro cycles description\"\n"
        "    }\n"
        "  ],\n"
        "  \"detailed_analysis\": {\n"
        "    \"focus_title\": \"Daily Focus Rhythm (e.g., Daily Night-Owl Schedule (6 Hours))\",\n"
        "    \"focus_description\": \"Detailed explanation of how and why study hours are divided into blocks.\",\n"
        "    \"focus_blocks\": [\n"
        "      {\"block\": \"Block 1 (Afternoon)\", \"time\": \"15:00 – 16:30\", \"mode\": \"Lighter review or reading\"}\n"
        "    ],\n"
        "    \"phases\": [\n"
        "      {\"title\": \"Phase 1: Deep Prep\", \"description\": \"Logic of this phase\", \"allocations\": [\"Block 1: Subject (Topic)\"]}\n"
        "    ],\n"
        "    \"pro_tips\": [\"Actionable academic tip\"],\n"
        "    \"subject_allocation_reasons\": {\"SubjectName\": \"Reason explaining hour allocation\"},\n"
        "    \"time_slot_reasons\": \"Explanation of time slots choices\",\n"
        "    \"milestone_reasons\": \"Explanation of exam proximity effect\",\n"
        "    \"preference_reasons\": \"Explanation of satisfying preferences\"\n"
        "  },\n"
        "  \"quality_scoring\": {\n"
        "    \"balance_score\": 80,\n"
        "    \"burnout_risk\": 20,\n"
        "    \"exam_readiness_score\": 90\n"
        "  }\n"
        "}\n\n"
        "Strict Rules & Constraints:\n"
        "1. Daily Quota Compliance & Weekday Consistency: You MUST schedule study sessions on EVERY weekday (Monday, Tuesday, Wednesday, Thursday, and Friday). Do NOT leave any weekday with 0 study hours. The sum of scheduled study hours for each of these weekdays must match the requested Daily Study Quota target within a strict tolerance of ±30 minutes (e.g. if daily quota is 7, the total hours for Monday, Tuesday, Wednesday, Thursday, and Friday must each be between 6.5 and 7.5 hours). Avoid under-allocations or leaving weekdays completely blank.\n"
        "2. STUDY HOUR DISTRIBUTION (Daily Quota Split): The requested daily study quota MUST be split and distributed across 2-4 study sessions throughout the day. You must NEVER place the entire quota into a single continuous study period (e.g., never schedule 7 hours consecutively). Interleave sessions with healthy recovery gaps.\n"
        "3. RECOVERY GAPS (Burnout Prevention): Between major study sessions, there MUST be recovery time. You must schedule a mandatory break/recovery gap of at least 60 minutes (preferred gap: 2-3 hours) between sessions. Do not schedule sessions back-to-back without a break.\n"
        "4. Sleeping Window: No study session is allowed between 12:00 AM (midnight) and 6:00 AM. For users with Night preference, the absolute no-study window is 3:00 AM to 7:00 AM.\n"
        "5. AVOID EARLY MORNINGS: If 'Avoid Early Mornings' is enabled, do NOT schedule any sessions before 9:00 AM. Preferred start windows are 9:00 AM onwards, 10:00 AM onwards, or 11:00 AM onwards.\n"
        "6. Each study session duration must correspond to complete Pomodoro/Deep Focus cycles: Classic Pomodoro: multiples of 0.5 hours; Deep Focus: multiples of 1.0 hour.\n"
        "7. Subject Rotation & Cognitive Load (Anti-Stacking & Mixing):\n"
        "   - Do NOT schedule identical subjects back-to-back on the same day.\n"
        "   - Do NOT stack multiple Hard subjects consecutively. Mix difficult and easier subjects, separated by breaks.\n"
        "8. Routine Calibration Weighting (Focus preference without dominating):\n"
        "   - Focus Period means 'most productive study window', NOT the 'only study window'.\n"
        "   - Weekend Preservation: If 'Weekend preservation: Yes' is specified, you MUST NOT schedule any study sessions on Saturday and Sunday (weekends remain completely free, 0 study hours). If 'Weekend preservation: No' is specified, Saturday and Sunday MUST receive study sessions, either matching the weekday daily quota or slightly reduced (e.g. 70-100% of daily quota). Do NOT leave weekends completely free of study sessions if 'Weekend preservation: No' is specified.\n"
        "   - Prioritize Critical Subjects: Allocate more hours and preferred slots to Hard subjects and subjects close to their exam dates.\n"
        "9. Chronological Phase Ordering: The preparation phases in `phases` MUST be ordered chronologically by milestone exam date. You MUST follow this exact order:\n"
        f"   - {milestones_chronology_str}\n"
        "10. Human Realism Safeguard (Human-like Scheduling): The generated schedule must feel like it was designed for a real college student.\n"
        "11. Respond with ONLY the raw JSON output, without any markdown formatting wrappers or conversational text."
    )

    user_prompt_1 = (
        f"Current Date: {current_date_str}\n\n"
        f"Generate the study schedule and detailed analysis for:\n\n"
        f"Subjects & Performance Analytics:\n{subjects_str}\n\n"
        f"Upcoming Exam Milestones:\n{milestones_str}\n\n"
        f"Fatigue Analytics:\n{fatigue_str}\n\n"
        f"Study Preferences & Constraints:\n{cal_str}\n\n"
        f"JSON output:"
    )

    requested_hours = calibration.get("daily_quota", 6)
    schedule_data = {}
    llm_calls_made = 0
    consistency_retries = 3
    
    for attempt in range(consistency_retries):
        try:
            logger.info(f"Executing Single-Call LLM Generation (Attempt {attempt + 1}).")
            llm_calls_made += 1
            schedule_data = call_llm_api(system_instruction_1, user_prompt_1)
            
            if not validate_schedule_json(schedule_data):
                raise ValueError("No valid schedule structure returned by LLM.")
                
            schedule_events = schedule_data.get("schedule", [])
            if weekend_preservation:
                schedule_events = enforce_weekend_preservation(schedule_events, milestones, requested_hours)
                schedule_data["schedule"] = schedule_events
            detailed_analysis = schedule_data.get("detailed_analysis", {})
            
            # Check consistency of the generated map
            if verify_consistency(schedule_events, detailed_analysis, milestones, subjects):
                break
            else:
                logger.warning(f"Consistency check failed on attempt {attempt + 1}. Retrying...")
                if attempt == consistency_retries - 1:
                    raise RuntimeError("Consistency check failed on all attempts.")
        except Exception as e:
            logger.error(f"Error in schedule generation attempt {attempt + 1}: {e}")
            if attempt == consistency_retries - 1:
                raise RuntimeError(f"AI Schedule Generation failed after all retries: {e}")

    logger.info(f"Total LLM calls made for this generation request: {llm_calls_made}")

    schedule_events = schedule_data.get("schedule", [])
    detailed_analysis = schedule_data.get("detailed_analysis", {})

    # Generate analytics locally using backend algorithms
    # This guarantees they are perfectly derived from the final generated schedule.
    logger.info("Computing metrics locally from the final schedule...")
    best_metrics = calculate_schedule_metrics(schedule_events, milestones, subjects, db=db)

    # Burnout Heuristics and self-correcting optimization
    if best_metrics.get("burnout_risk", 0) > 70:
        logger.info(f"Local Burnout risk {best_metrics['burnout_risk']}% is elevated. Running recovery rebalancer...")
        daily_events = {}
        for event in schedule_events:
            day = event.get("day")
            if day not in daily_events:
                daily_events[day] = []
            daily_events[day].append(event)
            
        for day, events in daily_events.items():
            day_hours = sum(float(e.get("hours", 0.0)) for e in events)
            if day_hours > 8.0:
                events.sort(key=lambda x: x.get("start_time", "00:00"))
                latest_event = events[-1]
                latest_event["session_type"] = "Recovery"
                latest_event["hours"] = max(0.5, latest_event.get("hours", 0.0) - 1.0)
                latest_event["reason"] = "Converted to Recovery block to mitigate elevated burnout risk."
                
                hard_count = 0
                for e in events:
                    sub_name = e.get("subject", "")
                    sub_obj = next((s for s in subjects if s.name.lower().strip() == sub_name.lower().strip()), None)
                    if sub_obj and sub_obj.difficulty == "Hard":
                        hard_count += 1
                        if hard_count >= 2:
                            e["session_type"] = "Revision"
                            e["hours"] = min(1.5, e["hours"])
                            e["reason"] = "Switched to Revision to prevent consecutive hard subjects."
                            hard_count = 0
                    else:
                        hard_count = 0
                        
        # Recalculate metrics locally
        best_metrics = calculate_schedule_metrics(schedule_events, milestones, subjects, db=db)

    # Compile transparency details
    actual_hours = sum(float(event.get("hours", 0.0)) for event in schedule_events)
    requested_hours = calibration.get("daily_quota", 6)
    
    recs = []
    if best_metrics["burnout_risk"] < 35:
        recs.append("Your burnout risk is Low. You have a balanced daily load with adequate rest.")
    elif best_metrics["burnout_risk"] < 60:
        recs.append("Your burnout risk is Moderate. Ensure you take full breaks between your study blocks.")
    else:
        recs.append("Your burnout risk is Elevated. We have automatically inserted recovery blocks and shifted hard subjects to optimize cognitive load.")
        
    if best_metrics["exam_readiness_score"] > 80:
        recs.append("Exam readiness is high! You have allocated sufficient preparation hours before your milestones.")
    else:
        recs.append("Readiness score is average. Consider adding more study hours before upcoming milestone exams.")
        
    ai_recommendation = " ".join(recs)
    
    transparency_data = {
        "requested_study_hours": requested_hours,
        "actual_study_hours": actual_hours,
        "predicted_burnout_risk": best_metrics["burnout_risk"],
        "predicted_exam_readiness": best_metrics["exam_readiness_score"],
        "ai_recommendation": ai_recommendation
    }

    # Force/Correct the focus schedule label
    focus_title = calculate_dynamic_schedule_label(schedule_events)
    detailed_analysis["focus_title"] = focus_title

    result = {
        "schedule": schedule_events,
        "detailed_analysis": detailed_analysis,
        "quality_scoring": best_metrics,
        "transparency": transparency_data,
        "is_cached": False,
        "llm_calls_count": llm_calls_made
    }

    # Save to Cache
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Saved generated schedule to cache: {cache_path}")
    except Exception as cache_save_err:
        logger.error(f"Failed to save schedule to cache: {cache_save_err}")
        
    return result
