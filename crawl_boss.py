import subprocess
import json
import csv
import sys
import queue
import threading
import argparse


def run_opencli(args):
    cmd = ["opencli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return None
    return result.stdout


def worker(q, results, lock):
    while True:
        task = q.get()
        if task is None:  # Sentinel to stop the worker
            q.task_done()
            break
        i, security_id, job = task
        print(f"[{i+1}] {job.get('name', security_id)}...")
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
        q.task_done()


def main():
    parser = argparse.ArgumentParser(description='Crawl Boss jobs with configurable thread count.')
    parser.add_argument('--threads', type=int, default=1, help='Number of threads to use for fetching job details (default: 1)')
    parser.add_argument('--limit', type=int, default=1, help='Number of jobs to fetch (default: 1)')
    args = parser.parse_args()

    search_args = [
        "boss", "search", "嵌入式",
        "--city", "南京",
        "--experience", "在校",
        "--degree", "本科",
        "--jobType", "实习",
        "--format", "json",
        "--limit", str(args.limit)
    ]

    print("Searching jobs...")
    output = run_opencli(search_args)
    if not output:
        return

    jobs = json.loads(output)
    if not isinstance(jobs, list):
        print("Unexpected output format", file=sys.stderr)
        return

    print(f"Found {len(jobs)} jobs, fetching details with {args.threads} threads...")

    # Prepare tasks: list of (i, security_id, job) for jobs with security_id
    tasks = []
    for i, job in enumerate(jobs):
        security_id = job.get("security_id")
        if security_id:
            tasks.append((i, security_id, job))

    if not tasks:
        print("No jobs with security_id to process")
        return

    # Create queue and results list
    q = queue.Queue()
    results = [None] * len(jobs)
    lock = threading.Lock()

    # Start worker threads
    threads = []
    for _ in range(args.threads):
        t = threading.Thread(target=worker, args=(q, results, lock))
        t.start()
        threads.append(t)

    # Put tasks into queue
    for task in tasks:
        q.put(task)

    # Put sentinels to stop workers
    for _ in range(args.threads):
        q.put(None)

    # Wait for all tasks to be done
    q.join()

    # Wait for threads to finish
    for t in threads:
        t.join()

    # Collect rows, skipping None (for jobs without security_id, but we handled that)
    rows = [result for result in results if result is not None]

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