# modules/course/showcase_adapter.py

from __future__ import annotations
import json
import os
import re
from typing import Any, Dict, List, Optional
from core.logger.service import LogService
from modules.course.dto import CourseDTO

SHOWCASE_BASE_JSON_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../course_showcase/base_courses_data.json")
)
SHOWCASE_JSON_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../course_showcase/courses_data.json")
)
SHOWCASE_JS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../course_showcase/js/courses_data.js")
)
SHOWCASE_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../course_showcase/showcase_config.json")
)
ASSETS_IMG_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../course_showcase/assets/images")
)

# Default Showcase Configuration
DEFAULT_SHOWCASE_CONFIG = {
    "recommended_course_ids": [
        "ms-cit",
        "tally-prime-with-gst",
        "python",
        "c-cpp-programming",
        "graphic-designing",
        "autocad",
    ],
    "trending_course_ids": [
        "ms-cit",
    ],
    "hidden_course_ids": [],
    "course_sections": {
        "ms-cit": "flagship",
        "tally-prime-with-gst": "accounting",
        "advanced-excel": "accounting",
        "graphic-designing": "design",
        "autocad": "design",
        "introduction-to-3d-animation": "design",
        "video-editing-techniques": "design",
        "desktop-publishing-adobe-and-coreldraw": "design",
        "content-illustration": "design",
        "python": "software",
        "c-cpp-programming": "software",
        "java": "software",
        "web-designing": "software",
        "php": "software",
        "ai-ml-basics": "emerging",
        "foundations-of-data-science-and-ai-with-python": "emerging",
        "digital-freelancing": "emerging",
        "cyber-security": "hardware",
        "it-desktop-support": "hardware",
        "it-network-support": "hardware",
        "data-entry-and-data-management": "office",
        "google-workspace-expert": "office",
        "office-assistance": "office",
        "english": "frontoffice",
        "soft-skills": "frontoffice",
        "it": "frontoffice",
    },
}

# Standard Track Configurations
TRACK_CONFIGS = {
    "flagship": {
        "accent": "#E11D48",
        "accent_light": "#FFE4E6",
        "gradient": "linear-gradient(135deg, #E11D48, #BE123C)",
        "default_tools": ["Windows 11", "MS Office 365", "ChatGPT & AI Tools", "Canva", "DigiLocker"],
        "default_roles": ["Computer Operator", "Office Executive", "Govt Exam Eligible"],
        "banner": "assets/images/ms-cit_showcase.webp",
        "thumb": "assets/images/ms-cit_thumb.webp",
    },
    "accounting": {
        "accent": "#059669",
        "accent_light": "#D1FAE5",
        "gradient": "linear-gradient(135deg, #059669, #047857)",
        "default_tools": ["TallyPrime 4.0", "GST Portal", "Advanced Excel", "E-Way Bills"],
        "default_roles": ["Accounts Executive", "Taxation Assistant", "Billing Operator"],
        "banner": "assets/images/tally-prime-with-gst_showcase.jpg",
        "thumb": "assets/images/tally-prime-with-gst_thumb.webp",
    },
    "design": {
        "accent": "#7C3AED",
        "accent_light": "#EDE9FE",
        "gradient": "linear-gradient(135deg, #7C3AED, #6D28D9)",
        "default_tools": ["Adobe Photoshop", "Illustrator", "CorelDRAW", "Canva Pro", "Figma"],
        "default_roles": ["Graphic Designer", "UI/UX Artist", "Brand Identity Designer"],
        "banner": "assets/images/graphic-designing_showcase.jpg",
        "thumb": "assets/images/graphic-designing_thumb.webp",
    },
    "software": {
        "accent": "#2563EB",
        "accent_light": "#DBEAFE",
        "gradient": "linear-gradient(135deg, #2563EB, #1D4ED8)",
        "default_tools": ["VS Code", "Git & GitHub", "Python", "HTML5/CSS3", "SQL Database"],
        "default_roles": ["Software Developer", "Web Developer", "Python Engineer"],
        "banner": "assets/images/python_showcase.jpg",
        "thumb": "assets/images/python_thumb.webp",
    },
    "emerging": {
        "accent": "#D97706",
        "accent_light": "#FEF3C7",
        "gradient": "linear-gradient(135deg, #D97706, #B45309)",
        "default_tools": ["Generative AI", "Prompt Engineering", "Pandas", "Data Visualization"],
        "default_roles": ["AI Prompt Specialist", "Junior Data Analyst", "Digital Freelancer"],
        "banner": "assets/images/ai-ml-basics_showcase.jpg",
        "thumb": "assets/images/ai-ml-basics_thumb.webp",
    },
    "hardware": {
        "accent": "#0284C7",
        "accent_light": "#E0F2FE",
        "gradient": "linear-gradient(135deg, #0284C7, #0369A1)",
        "default_tools": ["Hardware Diagnostics", "LAN/WAN Config", "Router & Switch", "Cyber Security Tools"],
        "default_roles": ["Desktop Support Engineer", "Network Technician", "IT Support Specialist"],
        "banner": "assets/images/desktop-support_showcase.jpg",
        "thumb": "assets/images/desktop-support_thumb.webp",
    },
    "office": {
        "accent": "#0D9488",
        "accent_light": "#CCFBF1",
        "gradient": "linear-gradient(135deg, #0D9488, #0F766E)",
        "default_tools": ["Google Workspace", "MS Excel Dashboards", "Email Etiquette", "Data Entry Tools"],
        "default_roles": ["Back Office Assistant", "MIS Executive", "Data Entry Operator"],
        "banner": "assets/images/google-workspace-expert_showcase.jpg",
        "thumb": "assets/images/google-workspace-expert_thumb.webp",
    },
    "frontoffice": {
        "accent": "#E11D48",
        "accent_light": "#FFE4E6",
        "gradient": "linear-gradient(135deg, #E11D48, #BE123C)",
        "default_tools": ["Spoken English Tools", "Business Email", "Presentation Softwares", "Interview Prep"],
        "default_roles": ["Customer Relationship Executive", "Front Office Coordinator", "Support Officer"],
        "banner": "assets/images/soft-skills_showcase.jpg",
        "thumb": "assets/images/soft-skills_thumb.webp",
    },
}

# MKCL Scraped Course ID to Standard SIMS Database Code Mapping
CATALOG_CODE_MAP = {
    "ms-cit": "MSCIT",
    "tally-prime-with-gst": "KLIC-TALLY",
    "advanced-excel": "KLIC-EXCEL",
    "graphic-designing": "KLIC-GRAPHIC",
    "autocad": "KLIC-AUTOCAD",
    "introduction-to-3d-animation": "KLIC-3DANIM",
    "video-editing-techniques": "KLIC-VIDEO",
    "desktop-publishing-adobe-and-coreldraw": "KLIC-DTP",
    "content-illustration": "KLIC-ILLUST",
    "python": "KLIC-PYTHON",
    "c-cpp-programming": "KLIC-CPP",
    "java": "KLIC-ADVJAVA",
    "web-designing": "KLIC-WEB",
    "php": "KLIC-PHP",
    "ai-ml-basics": "KLIC-AIML",
    "foundations-of-data-science-and-ai-with-python": "KLIC-DATASCI",
    "digital-freelancing": "KLIC-FREELANCE",
    "cyber-security": "KLIC-CYBER",
    "it-desktop-support": "KLIC-DESKTOP",
    "it-network-support": "KLIC-NETWORK",
    "data-entry-and-data-management": "KLIC-DATAENTRY",
    "google-workspace-expert": "KLIC-GWORKSPACE",
    "office-assistance": "KLIC-OFFICE",
    "english": "KLIC-ENGLISH",
    "soft-skills": "KLIC-SOFTSKILLS",
    "it": "KLIC-IT",
}

# Standard Default Fees for Courses
DEFAULT_FEES = {
    "MSCIT": 4500.0,
    "KLIC-TALLY": 5000.0,
    "KLIC-EXCEL": 4000.0,
    "KLIC-PYTHON": 5000.0,
    "KLIC-ADVJAVA": 5000.0,
    "KLIC-JAVA": 5000.0,
    "KLIC-CPP": 4500.0,
    "KLIC-WEB": 5000.0,
    "KLIC-GRAPHIC": 5500.0,
    "KLIC-AUTOCAD": 6000.0,
    "KLIC-3DANIM": 6500.0,
    "KLIC-VIDEO": 5500.0,
    "KLIC-DTP": 4500.0,
    "KLIC-ILLUST": 4500.0,
    "KLIC-PHP": 5000.0,
    "KLIC-AIML": 6000.0,
    "KLIC-DATASCI": 7000.0,
    "KLIC-FREELANCE": 4500.0,
    "KLIC-CYBER": 6500.0,
    "KLIC-DESKTOP": 5000.0,
    "KLIC-NETWORK": 5500.0,
    "KLIC-DATAENTRY": 3500.0,
    "KLIC-GWORKSPACE": 4000.0,
    "KLIC-OFFICE": 4000.0,
    "KLIC-ENGLISH": 3500.0,
    "KLIC-SOFTSKILLS": 3500.0,
    "KLIC-IT": 4000.0,
}


def normalize_token(text: str) -> str:
    """Strips non-alphanumeric chars and lowercases for fuzzy code/slug match."""
    return re.sub(r"[^a-zA-Z0-9]", "", text or "").lower()


def get_track_for_category(category: str, code: str = "", name: str = "") -> str:
    """Determines the appropriate showcase track ID based on category and course identity."""
    text = f"{category} {code} {name}".lower()
    if "mscit" in text or "it literacy" in text or "flagship" in text:
        return "flagship"
    if "account" in text or "tally" in text or "tax" in text or "finance" in text:
        return "accounting"
    if "design" in text or "creative" in text or "autocad" in text or "animation" in text or "video" in text or "dtp" in text:
        return "design"
    if "python" in text or "java" in text or "c++" in text or "cpp" in text or "web" in text or "software" in text or "programm" in text or "developer" in text:
        return "software"
    if "ai" in text or "data" in text or "machine" in text or "freelanc" in text or "emerging" in text:
        return "emerging"
    if "hardware" in text or "cyber" in text or "network" in text or "security" in text or "desktop" in text:
        return "hardware"
    if "office" in text or "workspace" in text or "entry" in text or "excel" in text:
        return "office"
    if "english" in text or "communication" in text or "soft skill" in text or "personality" in text:
        return "frontoffice"
    return "software"


def load_raw_catalog() -> List[Dict[str, Any]]:
    """Loads the base 27 MKCL authentic courses JSON."""
    path_to_load = SHOWCASE_BASE_JSON_PATH if os.path.exists(SHOWCASE_BASE_JSON_PATH) else SHOWCASE_JSON_PATH
    if os.path.exists(path_to_load):
        try:
            with open(path_to_load, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            LogService.error(f"Failed to load raw showcase json: {exc}", context="ShowcaseAdapter")
    return []


def sync_catalog_to_db(controller: Any) -> int:
    """
    Ensures all 27 authentic MKCL courses exist in the Master Database.
    Inserts missing courses without altering schema or overwriting user customizations.
    Returns count of newly inserted courses.
    """
    catalog = load_raw_catalog()
    if not catalog:
        return 0

    try:
        db_courses, _ = controller.list_courses(limit=500)
    except Exception as exc:
        LogService.error(f"Cannot list courses for sync: {exc}", context="ShowcaseAdapter")
        return 0

    existing_codes = {normalize_token(c.code): c for c in db_courses}
    existing_names = {normalize_token(c.name): c for c in db_courses}

    from core.security.context import SecurityContext
    from core.security.roles import Role

    had_user = SecurityContext.get_current_user_id() is not None
    current_role = SecurityContext.get_current_role()
    if not had_user or current_role != Role.ADMINISTRATOR.value:
        SecurityContext.set_current_user(user_id=1, username="system_bootstrap", role=Role.ADMINISTRATOR.value)

    added_count = 0
    try:
        for course_data in catalog:
            cid = course_data.get("id", "")
            assigned_code = CATALOG_CODE_MAP.get(cid, cid.replace("-", "").upper())
            course_name = course_data.get("title", cid.replace("-", " ").title())

            # Check if already exists by code or title
            norm_code = normalize_token(assigned_code)
            norm_name = normalize_token(course_name)

            if norm_code in existing_codes or norm_name in existing_names:
                continue

            # Prepare course payload
            category = course_data.get("category", "General")
            duration = course_data.get("duration", "2 Months")
            base_fee = DEFAULT_FEES.get(assigned_code, 4500.0)
            description = course_data.get("summary") or f"Official MKCL Career Track: {course_name}"

            payload = {
                "code": assigned_code,
                "name": course_name,
                "category": category,
                "duration": duration,
                "base_fee": base_fee,
                "status": "ACTIVE",
                "description": description,
            }

            try:
                controller.create_course(payload)
                added_count += 1
                existing_codes[norm_code] = True
                existing_names[norm_name] = True
                LogService.info(f"Synced catalog course into Master DB: {assigned_code} - {course_name}", context="ShowcaseAdapter")
            except Exception as exc:
                LogService.error(f"Failed to sync course {assigned_code}: {exc}", context="ShowcaseAdapter")
    finally:
        if not had_user:
            SecurityContext.clear()

    return added_count


def db_course_to_showcase(course: CourseDTO, extra_showcase: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Converts a CourseDTO (DB entity) into the rich Showcase format.
    Ensures all parent/student modes, tools, syllabus, and banners exist.
    """
    extra = extra_showcase or {}
    slug = re.sub(r"[^a-z0-9]+", "-", (course.code or course.name).lower()).strip("-")
    track_id = extra.get("track_id") or get_track_for_category(course.category, course.code, course.name)
    track_cfg = TRACK_CONFIGS.get(track_id, TRACK_CONFIGS["software"])

    tools = extra.get("tools") or track_cfg["default_tools"]
    job_roles = extra.get("job_roles") or track_cfg["default_roles"]
    salary_range = extra.get("salary_range") or f"₹{int(course.base_fee * 3):,} - ₹{int(course.base_fee * 6):,} / month"

    summary = course.description or f"Comprehensive practical training in {course.name}. Industry certified."
    
    parent_points = extra.get("parent_points") or [
        f"High career stability and strong employment demand in {course.category}.",
        f"State-recognized curriculum and Sudharm Infotech certified completion.",
        f"Fast return on investment with entry-level salary potential of {salary_range}.",
    ]

    counselor_points = extra.get("counselor_talking_points") or [
        f"Sudharm Infotech provides personalized guidance under Proff. Hemant Mahale.",
        "Regular weekly progress reports and dedicated practical lab hours.",
        "100% hands-on training to build verified confidence before placement.",
    ]

    student_projects = extra.get("student_projects") or [
        f"Real-world capstone portfolio project demonstrating {course.name} tools.",
        "Practical lab exercises with modern software workflows.",
        "Freelance job bidding and resume building workshop.",
    ]

    syllabus = extra.get("syllabus") or [
        f"Fundamentals of {course.name} & System Setup",
        "Essential Tools & Working Environment",
        "Practical Hands-on Workflows & Operations",
        "Industry Best Practices & Problem Solving",
        "Advanced Real-World Case Studies",
        "Capstone Portfolio Project Build",
        "Interview Preparation & Sudharm Certification Assessment",
    ]

    banner = extra.get("showcase_image") or track_cfg["banner"]
    thumb = extra.get("thumbnail") or track_cfg["thumb"]

    return {
        "id": slug,
        "db_id": course.id,
        "slug": slug,
        "code": course.code,
        "title": course.name,
        "category": course.category,
        "track_id": track_id,
        "badge": "MKCL Certified Program" if "klic" in course.code.lower() or "mscit" in course.code.lower() else "Sudharm Infotech Certified",
        "accent": track_cfg["accent"],
        "accent_light": track_cfg["accent_light"],
        "gradient": track_cfg["gradient"],
        "duration": course.duration or "2 Months",
        "base_fee": course.base_fee,
        "fee": f"₹{course.base_fee:,.0f}",
        "level": "Beginner to Advanced",
        "language": "English, Marathi, Hindi",
        "summary": summary,
        "certificate": "Authorized Learning Center Certification • Sudharm Infotech",
        "eligibility": "Open to Students, Job Seekers & Working Professionals",
        "tools": tools,
        "job_roles": job_roles,
        "salary_range": salary_range,
        "parent_points": parent_points,
        "counselor_talking_points": counselor_points,
        "student_projects": student_projects,
        "syllabus": syllabus,
        "syllabus_count": len(syllabus),
        "thumbnail": thumb,
        "showcase_image": banner,
        "official_url": "https://www.mkcl.org/courses/",
        "search_center_url": "https://www.mkcl.org/join",
        "is_active": course.is_active,
    }


format_db_course_to_showcase = db_course_to_showcase


def is_excluded_course(code: str, name: str) -> bool:
    """Returns True if the course is a test course, non-MKCL fake course, or fullstack duplicate."""
    c_up = (code or "").upper().replace("-", "").replace("_", "")
    n_low = (name or "").lower()
    test_prefixes = (
        "ACTLOG", "ADMCRS", "AUD", "BADPIN", "BATCHCRS", "CCH", "C1", "C2",
        "FEECHG", "ZEROFEE", "AT2", "INV", "NORSN", "OPSSUM", "DUPCODE",
        "EX1", "SAMEFEE", "SNAP", "SEARCH", "TESTCRS", "TOGGLE", "UPDCRS",
        "TSTPY", "TESTFULL", "EXAMPLE", "TEST", "TST",
    )
    return (
        any(c_up.startswith(p) for p in test_prefixes)
        or "test" in n_low
        or "fullstack" in n_low
        or "full stack" in n_low
        or "fullstack" in c_up.lower()
        or "fsd" in c_up.lower()
        or n_low in ("course one", "course two", "3d modelling")
    )


def get_all_showcase_courses(controller: Any) -> List[Dict[str, Any]]:
    """
    Returns the unified showcase course list.
    Merges base scraped MKCL catalog data with live database course records.
    Any new course created in DB by administrator is seamlessly formatted and included!
    """
    catalog = load_raw_catalog()
    catalog_by_id = {c.get("id"): c for c in catalog}
    
    # Map by normalized names and codes for matching
    catalog_by_norm = {}
    for c in catalog:
        norm_t = normalize_token(c.get("title", ""))
        norm_i = normalize_token(c.get("id", ""))
        catalog_by_norm[norm_t] = c
        catalog_by_norm[norm_i] = c

    try:
        db_courses, _ = controller.list_courses(limit=500)
    except Exception as exc:
        LogService.error(f"Failed to load courses from DB: {exc}", context="ShowcaseAdapter")
        return catalog

    unified_courses: List[Dict[str, Any]] = []
    matched_catalog_ids = set()

    # 1. Process all DB courses
    for db_c in db_courses:
        if is_excluded_course(db_c.code, db_c.name):
            continue

        norm_c = normalize_token(db_c.code)
        norm_n = normalize_token(db_c.name)

        matched_raw = None
        # Try finding in catalog code map
        for cid, assigned_code in CATALOG_CODE_MAP.items():
            if normalize_token(assigned_code) == norm_c:
                matched_raw = catalog_by_id.get(cid)
                break
        
        if not matched_raw:
            matched_raw = catalog_by_norm.get(norm_n) or catalog_by_norm.get(norm_c)

        if matched_raw:
            # Merge DB fields (fee, status, duration) into catalog data
            course_copy = dict(matched_raw)
            course_copy["db_id"] = db_c.id
            course_copy["code"] = db_c.code
            course_copy["base_fee"] = db_c.base_fee
            course_copy["fee"] = f"₹{db_c.base_fee:,.0f}"
            course_copy["duration"] = db_c.duration or course_copy.get("duration", "2 Months")
            course_copy["is_active"] = db_c.is_active
            unified_courses.append(course_copy)
            matched_catalog_ids.add(matched_raw.get("id"))
        else:
            # New custom course created by Administrator! Convert to showcase format
            showcase_item = db_course_to_showcase(db_c)
            unified_courses.append(showcase_item)

    # 2. Add any catalog courses that haven't been synced to DB yet
    for raw_c in catalog:
        if raw_c.get("id") not in matched_catalog_ids:
            course_copy = dict(raw_c)
            course_copy["code"] = CATALOG_CODE_MAP.get(raw_c.get("id"), raw_c.get("id", "").upper())
            course_copy["base_fee"] = DEFAULT_FEES.get(course_copy["code"], 4500.0)
            course_copy["fee"] = f"₹{course_copy['base_fee']:,.0f}"
            course_copy["is_active"] = True
            unified_courses.append(course_copy)

    cfg = load_showcase_config()
    rec_ids = set(cfg.get("recommended_course_ids", []))
    trending_ids = set(cfg.get("trending_course_ids", []))
    hidden_ids = set(cfg.get("hidden_course_ids", []))
    sections_map = cfg.get("course_sections", {})

    seen_ids = set()
    clean_courses: List[Dict[str, Any]] = []

    for c in unified_courses:
        cid = c.get("id")
        if not cid or cid in seen_ids:
            continue
        seen_ids.add(cid)
        c["is_recommended"] = cid in rec_ids
        c["is_trending"] = cid in trending_ids
        c["is_published_web"] = cid not in hidden_ids
        if cid in sections_map:
            c["track_id"] = sections_map[cid]
        if c.get("is_trending"):
            c["badge"] = "🔥 TRENDING"
        clean_courses.append(c)

    return clean_courses


def load_showcase_config() -> Dict[str, Any]:
    """Loads showcase configuration from showcase_config.json with default fallback."""
    if os.path.exists(SHOWCASE_CONFIG_PATH):
        try:
            with open(SHOWCASE_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in DEFAULT_SHOWCASE_CONFIG.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as exc:
            LogService.warn(f"Failed to read showcase config: {exc}", context="ShowcaseAdapter")
    return dict(DEFAULT_SHOWCASE_CONFIG)


def save_showcase_config(config: Dict[str, Any]) -> None:
    """Saves showcase configuration to showcase_config.json."""
    try:
        with open(SHOWCASE_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        LogService.info("Saved showcase config", context="ShowcaseAdapter")
    except Exception as exc:
        LogService.error(f"Failed to save showcase config: {exc}", context="ShowcaseAdapter")


def add_course_to_recommended(course_id: str) -> None:
    """Adds a course ID to the recommended courses list."""
    cfg = load_showcase_config()
    rec = cfg.get("recommended_course_ids", [])
    if course_id not in rec:
        rec.append(course_id)
        cfg["recommended_course_ids"] = rec
        save_showcase_config(cfg)


def remove_course_from_recommended(course_id: str) -> None:
    """Removes a course ID from the recommended courses list."""
    cfg = load_showcase_config()
    rec = cfg.get("recommended_course_ids", [])
    if course_id in rec:
        rec.remove(course_id)
        cfg["recommended_course_ids"] = rec
        save_showcase_config(cfg)


def toggle_course_trending(course_id: str) -> bool:
    """Toggles trending status for a course. Returns new trending state."""
    cfg = load_showcase_config()
    trending = cfg.get("trending_course_ids", [])
    if course_id in trending:
        trending.remove(course_id)
        is_trending = False
    else:
        trending.append(course_id)
        is_trending = True
    cfg["trending_course_ids"] = trending
    save_showcase_config(cfg)
    return is_trending


def toggle_course_web_visibility(course_id: str) -> bool:
    """Toggles website visibility for a course. Returns True if now visible."""
    cfg = load_showcase_config()
    hidden = cfg.get("hidden_course_ids", [])
    if course_id in hidden:
        hidden.remove(course_id)
        is_visible = True
    else:
        hidden.append(course_id)
        is_visible = False
    cfg["hidden_course_ids"] = hidden
    save_showcase_config(cfg)
    return is_visible


def set_course_section(course_id: str, section_id: str) -> None:
    """Assigns a course to a specific web section / track."""
    cfg = load_showcase_config()
    sections = cfg.get("course_sections", {})
    sections[course_id] = section_id
    cfg["course_sections"] = sections
    save_showcase_config(cfg)


def sync_showcase_web_stores(controller: Any) -> Dict[str, Any]:
    """
    Synchronizes the database courses and showcase configuration directly into
    courses_data.json and js/courses_data.js.
    Returns status summary.
    """
    courses = get_all_showcase_courses(controller)
    cfg = load_showcase_config()

    try:
        with open(SHOWCASE_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(courses, f, indent=2, ensure_ascii=False)

        with open(SHOWCASE_JS_PATH, "w", encoding="utf-8") as f:
            js_content = (
                "// Autogenerated course data store for SIMS Course Showcase\n"
                "window.COURSES_DATA = " + json.dumps(courses, indent=2, ensure_ascii=False) + ";\n"
                "window.MKCL_COURSES = window.COURSES_DATA;\n"
                "window.SHOWCASE_CONFIG = " + json.dumps(cfg, indent=2, ensure_ascii=False) + ";\n"
            )
            f.write(js_content)

        LogService.info(f"Successfully synced {len(courses)} courses to showcase web stores", context="ShowcaseAdapter")
        return {"success": True, "count": len(courses), "recommended": len(cfg.get("recommended_course_ids", []))}
    except Exception as exc:
        LogService.error(f"Failed to sync showcase web stores: {exc}", context="ShowcaseAdapter")
        return {"success": False, "error": str(exc)}


def persist_custom_course_to_showcase(course_dict: Dict[str, Any]) -> None:
    """
    Persists a new course into courses_data.json and js/courses_data.js.
    Ensures external browser presentation decks have access to newly created courses.
    """
    code = course_dict.get("code", "")
    title = course_dict.get("title", "")
    if is_excluded_course(code, title):
        LogService.info(f"Skipping persistence of excluded/test course: {code} - {title}", context="ShowcaseAdapter")
        return

    catalog = load_raw_catalog()
    existing_idx = next((i for i, c in enumerate(catalog) if c.get("id") == course_dict.get("id")), None)
    
    if existing_idx is not None:
        catalog[existing_idx] = course_dict
    else:
        catalog.append(course_dict)

    try:
        with open(SHOWCASE_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        
        # Also update js/courses_data.js
        with open(SHOWCASE_JS_PATH, "w", encoding="utf-8") as f:
            js_content = (
                "// Autogenerated course data store\n"
                "window.COURSES_DATA = " + json.dumps(catalog, indent=2, ensure_ascii=False) + ";\n"
                "window.MKCL_COURSES = window.COURSES_DATA;\n"
            )
            f.write(js_content)
        
        LogService.info(f"Persisted course {course_dict.get('id')} to showcase JSON & JS data stores", context="ShowcaseAdapter")
    except Exception as exc:
        LogService.error(f"Failed to persist course to showcase data store: {exc}", context="ShowcaseAdapter")
