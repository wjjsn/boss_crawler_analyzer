#!/usr/bin/env python3
"""
Batch Apply Script - Automatically apply to matched jobs
Uses the job database to find suitable positions and extract URLs for mass application
"""

import argparse
import json
import re
from typing import List, Dict, Any
from datetime import datetime

from job_database import (
    init_database, search_jobs, search_jobs_fts,
    get_all_cities, get_salary_stats,
    get_job_count, DATABASE_PATH
)


def normalize_skill(skill: str) -> str:
    """Normalize skill name for matching"""
    skill = skill.lower().strip()
    # Remove common variations
    replacements = {
        'c++': 'cplusplus',
        'c语言': 'c语言 c',
        '单片机': '单片机 stm32',
    }
    return skill


def extract_skills_from_description(description: str) -> List[str]:
    """Extract skill keywords from job description"""
    if not description:
        return []
    
    # Common embedded/skill keywords
    skill_keywords = [
        'python', 'c++', 'c语言', 'java', 'javascript', 'golang', 'rust', 'go',
        'stm32', 'fpga', 'dsp', 'arm', '单片机', '嵌入式', 'linux', 'rtos',
        'freertos', 'ucos', 'rt-thread', '驱动开发', '驱动', '内核', 'uboot',
        ' bootloader', 'makefile', 'cmake', 'gcc', 'ide', 'keil', 'iar',
        'iic', 'i2c', 'spi', 'uart', 'usb', 'can', 'rs232', 'rs485',
        'tcp', 'ip', 'udp', 'http', 'mqtt', 'modbus', '蓝牙', 'ble', 'wifi', 'zigbee',
        'lora', '4g', '5g', '通信', '协议',
        'ros', '机器人', '无人机', '自动驾驶',
        'pythorch', 'tensorflow', 'caffe', 'ai', '机器学习', '深度学习', '神经网络',
        'opencv', '图像处理', '计算机视觉', '算法',
        'rtos', '实时系统', '系统编程',
        'mcu', '微控制器', '芯片', '半导体',
        '电路', 'pcb', '原理图', '硬件', 'eda',
        'git', 'svn', '版本控制', 'ci/cd', 'docker', 'jenkins',
        'shell', 'bash', 'python脚本', '自动化测试',
        '数据结构', '算法', '计算机基础',
        'ucos', 'vxworks', 'qnx',
    ]
    
    description_lower = description.lower()
    found = []
    for skill in skill_keywords:
        if skill.lower() in description_lower:
            found.append(skill)
    return found


def match_jobs_by_skills(
    required_skills: List[str],
    exclude_skills: List[str] = None,
    city: str = None,
    min_salary: int = None,
    degree: str = None,
    limit: int = 50,
    db_path: str = None
) -> List[Dict[str, Any]]:
    """
    Match jobs based on required skills and optional filters.
    Jobs are scored based on skill match percentage.
    Skills are matched against both the 'skills' field and 'description' field.
    """
    exclude_skills = exclude_skills or []
    
    # Get all jobs with basic filters first
    jobs = search_jobs(
        city=city,
        min_salary=min_salary,
        degree=degree,
        limit=500,
        db_path=db_path
    )
    
    matched_jobs = []
    
    for job in jobs:
        # Get skills from JSON field
        job_skills = []
        if job.get('skills'):
            try:
                skills_val = job['skills']
                if isinstance(skills_val, str):
                    skills_list = json.loads(skills_val)
                else:
                    skills_list = skills_val
                if isinstance(skills_list, list):
                    job_skills = [s for s in skills_list if isinstance(s, str)]
            except (json.JSONDecodeError, TypeError, ValueError):
                job_skills = []
        
        # Also extract skills from description
        description = job.get('description', '') or ''
        desc_skills = extract_skills_from_description(description)
        
        # Combine all skills
        all_skills = job_skills + desc_skills
        if not all_skills and description:
            # If no known skills found, check if description contains any required skill keyword
            desc_lower = description.lower()
            desc_skills = [s for s in required_skills if s.lower() in desc_lower]
            all_skills = desc_skills
        
        # Convert to lowercase for matching
        all_skills_lower = [s.lower() for s in all_skills]
        required_lower = [s.lower() for s in required_skills]
        exclude_lower = [s.lower() for s in exclude_skills]
        
        # Check excluded skills (only if we have skills to check)
        if all_skills_lower:
            has_excluded = any(ex in all_skills_lower for ex in exclude_lower)
            if has_excluded:
                continue
        
        # Calculate match score
        matched_required = []
        missing_required = []
        for req in required_lower:
            if any(req in js for js in all_skills_lower):
                matched_required.append(req)
            else:
                missing_required.append(req)
        
        match_score = len(matched_required) / len(required_lower) if required_lower else 0
        
        # Bonus for having extra relevant skills
        extra_bonus = 0
        for js in all_skills_lower:
            for req in required_lower:
                if req in js and req not in matched_required:
                    extra_bonus += 0.05
                    break
        
        total_score = min(1.0, match_score + extra_bonus)
        
        # Include job if any required skill matches OR if no specific skills to match
        if matched_required or not required_skills:
            job['match_score'] = round(total_score, 3)
            job['matched_skills'] = list(set(matched_required))
            job['missing_skills'] = missing_required
            job['all_found_skills'] = list(set(all_skills))
            matched_jobs.append(job)
    
    # Sort by score
    matched_jobs.sort(key=lambda x: x['match_score'], reverse=True)
    
    return matched_jobs[:limit]


def get_job_urls(matched_jobs: List[Dict[str, Any]]) -> List[str]:
    """Extract URLs from matched jobs"""
    return [job['url'] for job in matched_jobs if job.get('url')]


def export_urls_to_file(urls: List[str], filename: str = "job_urls.txt") -> None:
    """Export URLs to a text file, one per line"""
    with open(filename, 'w', encoding='utf-8') as f:
        for url in urls:
            f.write(url + '\n')
    print(f"Exported {len(urls)} URLs to {filename}")


def display_matched_jobs(matched_jobs: List[Dict[str, Any]], show_details: bool = False) -> None:
    """Display matched jobs in a formatted way"""
    print("\n" + "=" * 80)
    print(f"Matched {len(matched_jobs)} jobs")
    print("=" * 80)
    
    for i, job in enumerate(matched_jobs[:20], 1):
        print(f"\n{i}. {job.get('company', 'Unknown')} - {job.get('name', 'Unknown')}")
        print(f"   Score: {job.get('match_score', 0):.1%}")
        print(f"   Salary: {job.get('salary', 'Not specified')}")
        print(f"   City: {job.get('city', 'Not specified')}")
        print(f"   Degree: {job.get('degree', 'Not specified')}")
        
        if show_details:
            print(f"   URL: {job.get('url', '')}")
            if job.get('matched_skills'):
                print(f"   Matched Skills: {', '.join(job['matched_skills'][:5])}")
            if job.get('all_found_skills'):
                print(f"   All Found: {', '.join(job['all_found_skills'][:8])}")
            if job.get('missing_skills'):
                print(f"   Missing Skills: {', '.join(job['missing_skills'][:3])}")


def query_interactive() -> None:
    """Interactive query mode"""
    print("\n" + "=" * 60)
    print("Job Matcher - Interactive Mode")
    print("=" * 60)
    
    cities = get_all_cities()
    print(f"\nAvailable cities: {', '.join(cities[:10])}{'...' if len(cities) > 10 else ''}")
    
    skills_input = input("\nEnter required skills (comma-separated): ").strip()
    if not skills_input:
        print("No skills entered, exiting.")
        return
    
    required_skills = [s.strip() for s in skills_input.split(',') if s.strip()]
    
    city = input("Enter city (or press Enter to skip): ").strip() or None
    min_salary_input = input("Enter minimum salary (元/天, or press Enter to skip): ").strip()
    
    min_salary = int(min_salary_input) if min_salary_input.isdigit() else None
    
    limit_input = input("Enter max results (default 50): ").strip()
    limit = int(limit_input) if limit_input.isdigit() else 50
    
    print("\nSearching...")
    matched = match_jobs_by_skills(
        required_skills=required_skills,
        city=city,
        min_salary=min_salary,
        limit=limit
    )
    
    display_matched_jobs(matched, show_details=True)
    
    if matched:
        export = input("\nExport URLs to file? (y/n): ").strip().lower()
        if export == 'y':
            filename = input("Enter filename (default: job_urls.txt): ").strip() or "job_urls.txt"
            urls = get_job_urls(matched)
            export_urls_to_file(urls, filename)
    
    print()


def generate_opencli_batch_script(urls: List[str], output_file: str = "batch_apply.sh") -> None:
    """Generate a shell script that uses opencli to batch apply"""
    job_urls = '\n'.join(f'    "{url}"' for url in urls)
    script = f"""#!/bin/bash
# Auto-generated batch application script
# Generated at: {datetime.now().isoformat()}

# Job URLs for batch application
JOBS=(
{job_urls}
)

echo "Found ${{#JOBS[@]}} jobs to apply"

for url in "${{JOBS[@]}}"; do
    echo "Applying to: $url"
    opencli boss detail "$url" --format json
    # Add your auto-apply logic here
    sleep 1
done

echo "Batch application completed!"
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(script)
    
    import os
    os.chmod(output_file, 0o755)
    print(f"Generated batch apply script: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Batch job matcher and URL extractor',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python batch_apply.py --interactive

  # Query by skills
  python batch_apply.py --skills "Python,C++,STM32" --city "广州"

  # Full-text search
  python batch_apply.py --search "嵌入式 Linux"

  # Export URLs to file
  python batch_apply.py --skills "Python,ROS" --export job_urls.txt
"""
    )
    
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Interactive query mode')
    parser.add_argument('--skills', '-s', type=str,
                        help='Comma-separated required skills (e.g., "Python,C++,STM32")')
    parser.add_argument('--exclude', '-e', type=str,
                        help='Comma-separated excluded skills')
    parser.add_argument('--city', '-c', type=str,
                        help='Filter by city')
    parser.add_argument('--min-salary', type=int,
                        help='Minimum salary (元/天)')
    parser.add_argument('--degree', '-d', type=str,
                        help='Required degree (e.g., "本科")')
    parser.add_argument('--search', type=str,
                        help='Full-text search keyword')
    parser.add_argument('--limit', type=int, default=50,
                        help='Maximum number of results (default: 50)')
    parser.add_argument('--export', '-o', type=str,
                        help='Export matched URLs to file')
    parser.add_argument('--script', action='store_true',
                        help='Generate opencli batch apply script')
    parser.add_argument('--db-path', type=str, default=DATABASE_PATH,
                        help='Path to SQLite database')
    
    args = parser.parse_args()
    
    init_database(args.db_path)
    
    if args.interactive or (not args.skills and not args.search):
        query_interactive()
        return
    
    required_skills = []
    if args.skills:
        required_skills = [s.strip() for s in args.skills.split(',') if s.strip()]
    
    exclude_skills = []
    if args.exclude:
        exclude_skills = [s.strip() for s in args.exclude.split(',') if s.strip()]
    
    if args.search:
        print(f"Full-text search: {args.search}")
        matched = search_jobs_fts(args.search, limit=args.limit, db_path=args.db_path)
        for job in matched:
            job['match_score'] = 1.0
    else:
        matched = match_jobs_by_skills(
            required_skills=required_skills,
            exclude_skills=exclude_skills,
            city=args.city,
            min_salary=args.min_salary,
            degree=args.degree,
            limit=args.limit,
            db_path=args.db_path
        )
    
    display_matched_jobs(matched, show_details=True)
    
    urls = get_job_urls(matched)
    
    if args.export:
        export_urls_to_file(urls, args.export)
    
    if args.script and urls:
        generate_opencli_batch_script(urls)
    
    print(f"\nTotal matched: {len(matched)} jobs")
    if urls:
        print(f"Total URLs: {len(urls)}")


if __name__ == "__main__":
    main()
