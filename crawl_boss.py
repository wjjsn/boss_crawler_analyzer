import os
import subprocess
import json
import csv
import sys
import queue
import threading
import argparse
import time
from tqdm import tqdm


def run_opencli(args, retries=0):
    cmd = ["opencli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        error_msg = result.stderr.lower()
        if any(kw in error_msg for kw in ["account", "异常", "auth", "登录", "权限", "unauthorized"]):
            tqdm.write(f"Account exception detected, retrying in 60 seconds... (attempt {retries + 1})", file=sys.stderr)
            time.sleep(60)
            return run_opencli(args, retries + 1)
        tqdm.write(f"Error: {' '.join(cmd)}", file=sys.stderr)
        tqdm.write(result.stderr, file=sys.stderr)
        return None
    return result.stdout


def fetch_batch_details(jobs, threads, pbar_job):
    tasks = []
    for i, job in enumerate(jobs):
        sid = job.get("security_id")
        if sid:
            tasks.append((i, sid, job))

    if not tasks:
        return []

    q = queue.Queue()
    results = [None] * len(jobs)
    lock = threading.Lock()

    def worker():
        while True:
            task = q.get()
            if task is None:
                q.task_done()
                break
            i, security_id, job = task
            # while True:
            detail_output = run_opencli(["boss", "detail", security_id, "--format", "json"])
            result=None
            if detail_output:
                try:
                    detail_list = json.loads(detail_output)
                    if isinstance(detail_list, list) and len(detail_list) > 0:
                        result = detail_list[0]
                    else:
                        result = job
                except json.JSONDecodeError:
                    pass

            with lock:
                results[i] = result
                pbar_job.update(1)
            q.task_done()

    thread_list = []
    for _ in range(threads):
        t = threading.Thread(target=worker)
        t.start()
        thread_list.append(t)

    for task in tasks:
        q.put(task)

    for _ in range(threads):
        q.put(None)

    q.join()
    for t in thread_list:
        t.join()

    return [r for r in results if r is not None]


MATRIX_CONFIG = {
    "city": ["南京", "北京", "上海", "杭州", "深圳", "广州", "成都", "武汉", "西安", "苏州"],
    "experience": ["在校生(实习)", "应届生(校招)", "经验不限", "1-3年", "3-5年"],
    "degree": ["本科", "硕士", "大专"],
    "jobType": ["实习", "全职"],
}


def matrix_crawl(query, limit_per_combo, threads, pbar_total, pbar_city, pbar_exp, pbar_deg, pbar_job, pbar_detail):
    all_rows = []
    seen_ids = set()

    cities = MATRIX_CONFIG["city"]
    experiences = MATRIX_CONFIG["experience"]
    degrees = MATRIX_CONFIG["degree"]
    job_types = MATRIX_CONFIG["jobType"]

    n_city = len(cities)
    n_exp = len(experiences)
    n_deg = len(degrees)
    n_job = len(job_types)
    total = n_city * n_exp * n_deg * n_job

    city_idx = 0
    for city in cities:
        pbar_city.set_postfix_str(f"{city} ({city_idx+1}/{n_city})")

        exp_idx = 0
        for exp in experiences:
            pbar_exp.set_postfix_str(f"{exp[:6]} ({exp_idx+1}/{n_exp})")

            deg_idx = 0
            for deg in degrees:
                pbar_deg.set_postfix_str(f"{deg} ({deg_idx+1}/{n_deg})")

                for job_idx, job_type in enumerate(job_types):
                    combo_no = city_idx * n_exp * n_deg * n_job + exp_idx * n_deg * n_job + deg_idx * n_job + job_idx + 1
                    pbar_total.update(1)
                    pbar_job.set_postfix_str(f"{job_type} ({job_idx+1}/{n_job}) [{combo_no}/{total}]")

                    search_args = [
                        "boss", "search", query,
                        "--city", city,
                        "--experience", exp,
                        "--degree", deg,
                        "--jobType", job_type,
                        "--format", "json",
                        "--limit", str(limit_per_combo)
                    ]

                    output = run_opencli(search_args)
                    jobs = []
                    if output:
                        try:
                            jobs = json.loads(output)
                            if isinstance(jobs, list):
                                new_jobs = []
                                for job in jobs:
                                    sid = job.get("security_id")
                                    if sid and sid not in seen_ids:
                                        seen_ids.add(sid)
                                        new_jobs.append(job)
                                jobs = new_jobs
                        except json.JSONDecodeError:
                            pass

                    if jobs:
                        pbar_detail.reset(len(jobs))
                        pbar_detail.set_postfix_str(f"0/{len(jobs)}")
                        rows = fetch_batch_details(jobs, threads, pbar_detail)
                        all_rows.extend(rows)
                        pbar_detail.set_postfix_str(f"{len(rows)}/{len(jobs)}")

                        existing = []
                        if os.path.exists("boss_jobs.json"):
                            try:
                                with open("boss_jobs.json", "r", encoding="utf-8") as f:
                                    existing = json.load(f)
                            except (json.JSONDecodeError, Exception):
                                existing = []
                        with open("boss_jobs.json", "w", encoding="utf-8") as f:
                            json.dump(existing + all_rows, f, ensure_ascii=False, indent=4)

                deg_idx += 1

            exp_idx += 1

        city_idx += 1

    pbar_total.close()
    pbar_city.close()
    pbar_exp.close()
    pbar_deg.close()
    pbar_job.close()
    pbar_detail.close()

    return all_rows


def main():
    parser = argparse.ArgumentParser(description='Matrix crawl Boss jobs.')
    parser.add_argument('--query', type=str, default="嵌入式", help='Search query')
    parser.add_argument('--threads', type=int, default=1, help='Number of threads')
    parser.add_argument('--limit', type=int, default=30, help='Limit per combination')
    parser.add_argument('--city', nargs='*', help='Override cities')
    parser.add_argument('--experience', nargs='*', help='Override experience')
    parser.add_argument('--degree', nargs='*', help='Override degree')
    parser.add_argument('--jobType', nargs='*', help='Override jobType')
    args = parser.parse_args()

    if args.city:
        MATRIX_CONFIG["city"] = args.city
    if args.experience:
        MATRIX_CONFIG["experience"] = args.experience
    if args.degree:
        MATRIX_CONFIG["degree"] = args.degree
    if args.jobType:
        MATRIX_CONFIG["jobType"] = args.jobType

    print(f"Query: {args.query}, Threads: {args.threads}, Limit per combo: {args.limit}")
    print(f"\nMatrix config:")
    for key in MATRIX_CONFIG:
        print(f"  {key}: {MATRIX_CONFIG[key]}")

    n_city = len(MATRIX_CONFIG["city"])
    n_exp = len(MATRIX_CONFIG["experience"])
    n_deg = len(MATRIX_CONFIG["degree"])
    n_job = len(MATRIX_CONFIG["jobType"])
    total = n_city * n_exp * n_deg * n_job

    print(f"\nTotal combinations: {total}")
    print(f"  City: {n_city}, Experience: {n_exp}, Degree: {n_deg}, JobType: {n_job}\n")

    pbar_total = tqdm(total=total, desc="总矩阵", unit="combo", position=0)
    pbar_city = tqdm(total=n_city, desc="City", unit="city", position=1)
    pbar_exp = tqdm(total=n_exp, desc="Experience", unit="exp", position=2)
    pbar_deg = tqdm(total=n_deg, desc="Degree", unit="deg", position=3)
    pbar_job = tqdm(total=n_job, desc="JobType", unit="job", position=4)
    pbar_detail = tqdm(total=0, desc="Fetching details", unit="job", position=5)

    rows = matrix_crawl(args.query, args.limit, args.threads, pbar_total, pbar_city, pbar_exp, pbar_deg, pbar_job, pbar_detail)

    if not rows:
        print("No jobs to save")
        return

    csv_path = "boss_jobs.csv"
    fieldnames = list(dict.fromkeys(k for row in rows for k in row.keys()))
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} jobs to {csv_path}")


if __name__ == "__main__":
    main()