import subprocess
import json
import csv
import sys
import queue
import threading
import argparse
import difflib
import os
from pathlib import Path
from tqdm import tqdm


EXCLUDE_FIELDS = {"active_time", "url"}

# 热门城市列表（Boss直聘支持的中文城市名）
HOT_CITIES = [
    "北京", "上海", "广州", "深圳",
    "杭州", "成都", "武汉", "南京",
    "西安", "苏州", "长沙", "郑州",
    "东莞", "佛山", "合肥", "青岛",
    "大连", "厦门", "天津", "宁波",
    "沈阳", "昆明", "福州", "济南",
    "哈尔滨", "长春", "石家庄", "南昌",
    "贵阳", "太原", "兰州", "呼和浩特",
]


def compute_similarity(a, b):
    fields_a = {k: v for k, v in a.items() if k not in EXCLUDE_FIELDS}
    fields_b = {k: v for k, v in b.items() if k not in EXCLUDE_FIELDS}
    all_keys = set(fields_a.keys()) | set(fields_b.keys())
    total_ratio = 0.0
    for key in all_keys:
        v1 = str(fields_a.get(key, ""))
        v2 = str(fields_b.get(key, ""))
        total_ratio += difflib.SequenceMatcher(None, v1, v2).ratio()
    return total_ratio / len(all_keys) if all_keys else 0.0


def run_opencli(args):
    cmd = ["opencli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return None
    return result.stdout


def worker(q, results, lock, pbar):
    while True:
        task = q.get()
        if task is None:  # Sentinel to stop the worker
            q.task_done()
            break
        i, security_id, job = task
        detail_output = run_opencli(["boss", "detail", security_id, "--format", "json"])

        if detail_output:
            try:
                detail_list = json.loads(detail_output)
                if isinstance(detail_list, list) and len(detail_list) > 0:
                    result = detail_list[0]
                else:
                    result = job
            except json.JSONDecodeError:
                result = job
        else:
            result = job

        with lock:
            results[i] = result
        pbar.update(1)
        q.task_done()


def run_search(city, limit):
    """Run boss search for a specific city and return jobs."""
    search_args = [
        "boss", "search", "嵌入式",
        "--city", city,
        "--experience", "在校",
        "--degree", "本科",
        "--jobType", "实习",
        "--format", "json",
        "--limit", str(limit)
    ]
    output = run_opencli(search_args)
    if not output:
        return []
    try:
        jobs = json.loads(output)
        return jobs if isinstance(jobs, list) else []
    except json.JSONDecodeError:
        return []


def run_detail(security_id, job):
    """Fetch job detail and merge with existing job data."""
    detail_output = run_opencli(["boss", "detail", security_id, "--format", "json"])
    if detail_output:
        try:
            detail_list = json.loads(detail_output)
            if isinstance(detail_list, list) and len(detail_list) > 0:
                return detail_list[0]
        except json.JSONDecodeError:
            pass
    return job


def fetch_all_details(jobs, threads):
    """Fetch details for all jobs using thread pool."""
    tasks = [(i, job.get("security_id"), job)
             for i, job in enumerate(jobs) if job.get("security_id")]
    if not tasks:
        return jobs

    q = queue.Queue()
    results = [None] * len(jobs)
    lock = threading.Lock()

    with tqdm(total=len(tasks), desc="获取岗位详情", unit="个") as pbar:
        def worker_thread():
            while True:
                task = q.get()
                if task is None:
                    q.task_done()
                    break
                i, security_id, job = task
                results[i] = run_detail(security_id, job)
                pbar.update(1)
                q.task_done()

        thread_list = [threading.Thread(target=worker_thread) for _ in range(threads)]
        for t in thread_list:
            t.start()
        for task in tasks:
            q.put(task)
        for _ in range(threads):
            q.put(None)
        for t in thread_list:
            t.join()
    return [r if r is not None else jobs[i] for i, r in enumerate(results)]


def load_existing(path):
    """Load existing jobs from file, keyed by URL."""
    if not os.path.exists(path):
        return {}
    try:
        data = json.load(open(path, "r", encoding="utf-8"))
        if isinstance(data, list):
            return {str(job.get("url", f"__unknown_{i}")): job
                    for i, job in enumerate(data)}
        return {}
    except (json.JSONDecodeError, IOError):
        return {}


def merge_jobs(existing, new_rows):
    """Merge new rows with existing jobs (dedup by URL, keep active_time)."""
    url_to_index = {}
    for idx, row in enumerate(new_rows):
        url = row.get("url")
        if url:
            url_to_index[url] = idx

    for old_job in existing.values():
        old_url = old_job.get("url")
        if old_url and old_url in url_to_index:
            new_job = new_rows[url_to_index[old_url]]
            sim = compute_similarity(old_job, new_job)
            if sim >= 0.9:
                new_job["active_time"] = old_job.get("active_time", new_job.get("active_time"))
            new_rows[url_to_index[old_url]] = new_job

    # Add old jobs not present in new rows
    new_urls = set(url_to_index.keys())
    for old_url, old_job in existing.items():
        if old_url not in new_urls:
            new_rows.append(old_job)
    return new_rows


def save_results(rows, csv_path="boss_jobs.csv", json_path="boss_jobs.json"):
    """Save rows to CSV and JSON, preserving existing data."""
    if not rows:
        return

    # Deduplicate by URL
    seen = set()
    unique = []
    for r in rows:
        url = r.get("url")
        if url and url not in seen:
            seen.add(url)
            unique.append(r)
    rows = unique

    # Save JSON
    json.dump(rows, open(json_path, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

    # Save CSV
    fieldnames = list(dict.fromkeys(k for row in rows for k in row.keys()))
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  -> Saved {len(rows)} jobs")


def main():
    parser = argparse.ArgumentParser(description='Crawl Boss jobs with configurable thread count.')
    parser.add_argument('--threads', type=int, default=1,
                        help='Number of threads to use for fetching job details (default: 1)')
    parser.add_argument('--limit', type=int, default=500,
                        help='Max jobs per city (default: 500)')
    parser.add_argument('--cities', nargs='*', default=None,
                        help='Specific cities to crawl. Defaults to all hot cities.')
    parser.add_argument('--keyword', default="嵌入式",
                        help='Search keyword (default: 嵌入式)')
    args = parser.parse_args()

    cities = args.cities if args.cities else HOT_CITIES
    limit = max(1, args.limit)

    # Load all existing data once
    existing = load_existing("boss_jobs.json")
    print(f"Loaded {len(existing)} existing jobs")

    all_new_rows = []

    for city in cities:
        print(f"\n=== Crawling city: {city} (limit={limit}) ===")
        jobs = run_search(city, limit)
        if not jobs:
            print(f"  No jobs found in {city}, skipping...")
            continue
        print(f"  Found {len(jobs)} jobs, fetching details...")
        rows = fetch_all_details(jobs, args.threads)
        print(f"  Fetched details for {len(rows)} jobs in {city}")
        all_new_rows.extend(rows)

    if not all_new_rows:
        print("No new jobs collected.")
        return

    print(f"\n=== Merging {len(all_new_rows)} new jobs with existing ===")
    merged = merge_jobs(existing, all_new_rows)
    print(f"Total after merge: {len(merged)} unique jobs")

    save_results(merged)


if __name__ == "__main__":
    main()
