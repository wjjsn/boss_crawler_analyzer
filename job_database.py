"""
Job Database Module - SQLite database for job listings
Provides storage, querying, and AI-assisted job matching capabilities
Uses only Python standard library
"""

import sqlite3
import json
import os
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

DATABASE_PATH = "jobs.db"

# Schema definition
SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    security_id TEXT,
    url TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    salary TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_type TEXT,
    company TEXT NOT NULL,
    area TEXT,
    district TEXT,
    city TEXT,
    experience TEXT,
    degree TEXT,
    description TEXT,
    skills TEXT,
    boss_name TEXT,
    boss_title TEXT,
    boss_online TEXT,
    industry TEXT,
    scale TEXT,
    stage TEXT,
    welfare TEXT,
    address TEXT,
    active_time TEXT,
    city_raw TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_city ON jobs(city);
CREATE INDEX IF NOT EXISTS idx_jobs_name ON jobs(name);
CREATE INDEX IF NOT EXISTS idx_jobs_salary_min ON jobs(salary_min);
CREATE INDEX IF NOT EXISTS idx_jobs_salary_max ON jobs(salary_max);
CREATE INDEX IF NOT EXISTS idx_jobs_degree ON jobs(degree);
CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url);
"""

# FTS Schema
FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
    name, company, area, city, description, skills,
    content='jobs',
    content_rowid='id'
);
"""


@contextmanager
def get_db_connection(db_path: str = DATABASE_PATH):
    """Context manager for database connections"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database(db_path: str = DATABASE_PATH) -> None:
    """Initialize database with schema"""
    with get_db_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.executescript(FTS_SCHEMA)
        # Insert triggers
        conn.executescript("""
            CREATE TRIGGER IF NOT EXISTS jobs_ai AFTER INSERT ON jobs BEGIN
                INSERT INTO jobs_fts(rowid, name, company, area, city, description, skills)
                VALUES (new.id, new.name, new.company, new.area, new.city, new.description, new.skills);
            END;
            
            CREATE TRIGGER IF NOT EXISTS jobs_ad AFTER DELETE ON jobs BEGIN
                INSERT INTO jobs_fts(jobs_fts, rowid, name, company, area, city, description, skills)
                VALUES ('delete', old.id, old.name, old.company, old.area, old.city, old.description, old.skills);
            END;
            
            CREATE TRIGGER IF NOT EXISTS jobs_au AFTER UPDATE ON jobs BEGIN
                INSERT INTO jobs_fts(jobs_fts, rowid, name, company, area, city, description, skills)
                VALUES ('delete', old.id, old.name, old.company, old.area, old.city, old.description, old.skills);
                INSERT INTO jobs_fts(rowid, name, company, area, city, description, skills)
                VALUES (new.id, new.name, new.company, new.area, new.city, new.description, new.skills);
            END;
        """)


def parse_salary(salary_str: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """Parse salary string like '150-250元/天' into min, max, type"""
    if not salary_str:
        return None, None, None
    
    salary_str = str(salary_str).strip()
    
    match = re.match(r'(\d+)-(\d+)元/天', salary_str)
    if match:
        return int(match.group(1)), int(match.group(2)), 'daily'
    
    match = re.match(r'(\d+)-(\d+)元/月', salary_str)
    if match:
        return int(match.group(1)), int(match.group(2)), 'monthly'
    
    match = re.match(r'(\d+)k-(\d+)k', salary_str, re.IGNORECASE)
    if match:
        return int(match.group(1)) * 1000, int(match.group(2)) * 1000, 'yearly'
    
    return None, None, None


def normalize_city(area_str: str) -> str:
    """Extract city name from area string like '广州·番禺区·大石'"""
    if not area_str:
        return ''
    area_str = str(area_str).strip()
    if '·' in area_str:
        return area_str.split('·')[0]
    return area_str


def job_to_record(job: Dict[str, Any]) -> Dict[str, Any]:
    """Convert job dict to database record format"""
    salary_str = job.get('salary', '')
    salary_min, salary_max, salary_type = parse_salary(salary_str)
    
    city = normalize_city(job.get('area', '') or job.get('city', ''))
    
    skills = job.get('skills', '')
    if isinstance(skills, list):
        skills = json.dumps(skills, ensure_ascii=False)
    
    welfare = job.get('welfare', '')
    if isinstance(welfare, list):
        welfare = json.dumps(welfare, ensure_ascii=False)
    
    return {
        'security_id': job.get('security_id'),
        'url': job.get('url', ''),
        'name': job.get('name', ''),
        'salary': salary_str,
        'salary_min': salary_min,
        'salary_max': salary_max,
        'salary_type': salary_type,
        'company': job.get('company', ''),
        'area': job.get('area', ''),
        'district': job.get('district', ''),
        'city': city,
        'experience': job.get('experience', ''),
        'degree': job.get('degree', ''),
        'description': job.get('description', ''),
        'skills': skills,
        'boss_name': job.get('boss_name', ''),
        'boss_title': job.get('boss_title', ''),
        'boss_online': job.get('bossOnline', ''),
        'industry': job.get('industry', ''),
        'scale': job.get('scale', ''),
        'stage': job.get('stage', ''),
        'welfare': welfare,
        'address': job.get('address', ''),
        'active_time': job.get('active_time', ''),
        'city_raw': job.get('city', ''),
    }


def insert_job(job: Dict[str, Any], db_path: str = DATABASE_PATH) -> int:
    """Insert a single job and return its ID"""
    record = job_to_record(job)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO jobs (
                security_id, url, name, salary, salary_min, salary_max, salary_type,
                company, area, district, city, experience, degree, description,
                skills, boss_name, boss_title, boss_online, industry, scale, stage,
                welfare, address, active_time, city_raw, updated_at
            ) VALUES (
                :security_id, :url, :name, :salary, :salary_min, :salary_max, :salary_type,
                :company, :area, :district, :city, :experience, :degree, :description,
                :skills, :boss_name, :boss_title, :boss_online, :industry, :scale, :stage,
                :welfare, :address, :active_time, :city_raw, CURRENT_TIMESTAMP
            )
        """, record)
        return cursor.lastrowid


def insert_jobs_batch(jobs: List[Dict[str, Any]], db_path: str = DATABASE_PATH) -> int:
    """Insert multiple jobs, return count of inserted/updated"""
    count = 0
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        for job in jobs:
            record = job_to_record(job)
            cursor.execute("""
                INSERT OR REPLACE INTO jobs (
                    security_id, url, name, salary, salary_min, salary_max, salary_type,
                    company, area, district, city, experience, degree, description,
                    skills, boss_name, boss_title, boss_online, industry, scale, stage,
                    welfare, address, active_time, city_raw, updated_at
                ) VALUES (
                    :security_id, :url, :name, :salary, :salary_min, :salary_max, :salary_type,
                    :company, :area, :district, :city, :experience, :degree, :description,
                    :skills, :boss_name, :boss_title, :boss_online, :industry, :scale, :stage,
                    :welfare, :address, :active_time, :city_raw, CURRENT_TIMESTAMP
                )
            """, record)
            count += 1
    return count


def search_jobs(
    keyword: str = None,
    city: str = None,
    company: str = None,
    min_salary: int = None,
    max_salary: int = None,
    degree: str = None,
    skills: List[str] = None,
    limit: int = 50,
    db_path: str = DATABASE_PATH
) -> List[Dict[str, Any]]:
    """Search jobs with various filters"""
    conditions = []
    params = []
    
    if keyword:
        conditions.append("(name LIKE ? OR company LIKE ? OR description LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
    
    if city:
        conditions.append("city = ?")
        params.append(city)
    
    if company:
        conditions.append("company LIKE ?")
        params.append(f"%{company}%")
    
    if min_salary is not None:
        conditions.append("salary_max >= ?")
        params.append(min_salary)
    
    if max_salary is not None:
        conditions.append("salary_min <= ?")
        params.append(max_salary)
    
    if degree:
        conditions.append("degree = ?")
        params.append(degree)
    
    if skills:
        skill_conditions = " OR ".join(["skills LIKE ?" for _ in skills])
        conditions.append(f"({skill_conditions})")
        params.extend([f"%{s}%" for s in skills])
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = f"""
        SELECT * FROM jobs 
        WHERE {where_clause}
        ORDER BY updated_at DESC
        LIMIT ?
    """
    params.append(limit)
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def search_jobs_fts(keyword: str, limit: int = 50, db_path: str = DATABASE_PATH) -> List[Dict[str, Any]]:
    """Full-text search on jobs"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT jobs.* FROM jobs_fts
            JOIN jobs ON jobs.rowid = jobs_fts.rowid
            WHERE jobs_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (keyword, limit))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_job_by_url(url: str, db_path: str = DATABASE_PATH) -> Optional[Dict[str, Any]]:
    """Get a single job by URL"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE url = ?", (url,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_job_count(db_path: str = DATABASE_PATH) -> int:
    """Get total job count"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs")
        return cursor.fetchone()[0]


def get_all_cities(db_path: str = DATABASE_PATH) -> List[str]:
    """Get all unique cities"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT city FROM jobs WHERE city != '' ORDER BY city")
        return [row[0] for row in cursor.fetchall()]


def get_all_companies(db_path: str = DATABASE_PATH) -> List[str]:
    """Get all unique companies"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT company FROM jobs WHERE company != '' ORDER BY company")
        return [row[0] for row in cursor.fetchall()]


def get_salary_stats(db_path: str = DATABASE_PATH) -> Dict[str, Any]:
    """Get salary statistics"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                AVG(salary_min) as avg_min,
                AVG(salary_max) as avg_max,
                MAX(salary_max) as max_salary,
                MIN(salary_min) as min_salary
            FROM jobs WHERE salary_min IS NOT NULL
        """)
        row = cursor.fetchone()
        return dict(row) if row else {}


def get_skills_stats(db_path: str = DATABASE_PATH) -> List[Dict[str, Any]]:
    """Get skill occurrence statistics from stored skills"""
    from collections import Counter
    skill_counts = Counter()
    
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT skills FROM jobs WHERE skills IS NOT NULL AND skills != ''")
        
        for (skills_str,) in cursor.fetchall():
            try:
                skills_list = json.loads(skills_str)
                if isinstance(skills_list, list):
                    for s in skills_list:
                        if isinstance(s, str):
                            skill_counts[s.strip()] += 1
            except (json.JSONDecodeError, TypeError):
                pass
    
    return [
        {'skill': s, 'count': c}
        for s, c in skill_counts.most_common(100)
    ]


def import_from_json(json_path: str, db_path: str = DATABASE_PATH) -> int:
    """Import jobs from JSON file into database"""
    with open(json_path, 'r', encoding='utf-8') as f:
        jobs = json.load(f)
    
    if not isinstance(jobs, list):
        raise ValueError("JSON file must contain a list of jobs")
    
    count = insert_jobs_batch(jobs, db_path)
    return count


def export_to_json(db_path: str = DATABASE_PATH, json_path: str = "jobs_export.json") -> int:
    """Export all jobs from database to JSON"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs")
        columns = [desc[0] for desc in cursor.description]
        jobs = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        for job in jobs:
            for key in ['welfare', 'skills']:
                if key in job and job[key]:
                    try:
                        job[key] = json.loads(job[key]) if isinstance(job[key], str) else job[key]
                    except (json.JSONDecodeError, TypeError):
                        pass
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        
        return len(jobs)


def delete_job(job_id: int, db_path: str = DATABASE_PATH) -> bool:
    """Delete a job by ID"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return cursor.rowcount > 0


def clear_database(db_path: str = DATABASE_PATH) -> int:
    """Clear all jobs from database"""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs")
        count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM jobs")
        return count


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert sqlite3.Row to dict"""
    return dict(row)


if __name__ == "__main__":
    print("Initializing job database...")
    init_database()
    print(f"Database initialized at {DATABASE_PATH}")
    
    if os.path.exists("boss_jobs.json"):
        print("\nImporting jobs from boss_jobs.json...")
        count = import_from_json("boss_jobs.json")
        print(f"Imported {count} jobs")
        
        print(f"\nDatabase contains {get_job_count()} jobs")
        print(f"Cities: {get_all_cities()}")
        stats = get_salary_stats()
        print(f"Salary stats: avg_min={stats.get('avg_min')}, avg_max={stats.get('avg_max')}")
    else:
        print("\nNo boss_jobs.json found, run crawl_boss.py first to populate data")
