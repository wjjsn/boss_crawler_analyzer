import subprocess
import json
import csv
import sys


def run_opencli(args):
    cmd = ["opencli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {' '.join(cmd)}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return None
    return result.stdout


def main():
    search_args = [
        "boss", "search", "嵌入式",
        "--city", "南京",
        "--experience", "在校",
        "--degree", "本科",
        "--jobType", "实习",
        "--format", "json",
        "--limit", "10"
    ]

    print("Searching jobs...")
    output = run_opencli(search_args)
    if not output:
        return

    jobs = json.loads(output)
    if not isinstance(jobs, list):
        print("Unexpected output format", file=sys.stderr)
        return

    print(f"Found {len(jobs)} jobs, fetching details...")

    rows = []
    for i, job in enumerate(jobs):
        security_id = job.get("security_id")
        if not security_id:
            continue

        print(f"[{i+1}/{len(jobs)}] {job.get('name', security_id)}...")
        detail_output = run_opencli(["boss", "detail", security_id, "--format", "json"])

        if detail_output:
            try:
                detail_list = json.loads(detail_output)
                if isinstance(detail_list, list) and len(detail_list) > 0:
                    rows.append(detail_list[0])
                else:
                    rows.append(job)
            except json.JSONDecodeError:
                rows.append(job)
        else:
            rows.append(job)

    if not rows:
        print("No jobs to save")
        return

    csv_path = "boss_jobs.csv"
    fieldnames = list(rows[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} jobs to {csv_path}")


if __name__ == "__main__":
    main()