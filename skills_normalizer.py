import json
import time
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")

if not BASE_URL or not API_KEY:
    print("请在 .env 文件中配置 BASE_URL 和 API_KEY")
    exit(1)

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SCORE_GUIDE = """
评分标准（0.0-5.0分）：
- 0.0分：完全不要求，或明确说不需要
- 1.0分：仅作为加分项/优先项，不是必须（如"优先""加分项"）
- 2.0分：一般了解/会用即可（如"了解""熟悉基础""接触过"）
- 3.0分：需要日常使用，能独立完成常规任务（如"熟练""独立开发""有过经验"）
- 4.0分：深度掌握，能解决复杂问题（如"精通""深入""底层"）
- 5.0分：专家级别，能架构设计/攻坚难题（如"专家""架构""源码级"）
"""

PROMPT_TEMPLATE = """
你是招聘数据分析专家。请从岗位描述和技能要求中：

1. 提取所有提到的【技术技能】（包括编程语言、框架、工具、硬件等）
2. 按评分标准给每个技能打分

{score_guide}

请只输出JSON格式，结构如下：
{{
  "skills": [
    {{"name": "技能名称", "score": 分数}},
    {{"name": "技能名称", "score": 分数}}
  ]
}}

注意：
- 技能名称用标准写法，如 "C++"/"Python"/"STM32"/"RTOS"/"Linux"
- 同义技能合并（如"C"/"C语言"都写成"C"，"STM32开发"/"STM32"都写成"STM32"）
- 删除无意义的标签（如"弹性时间"、"支持远程办公"）
- 保留专业背景（如"计算机相关专业"）和软技能（如"英语读写能力良好"）
- 只保留有区分度的技术技能
- score 分数范围 0.0-5.0

岗位信息：
岗位名称：{name}
岗位描述：{description}
原始技能要求：{skills}
"""


def extract_skills(name: str, description: str, skills: str, retry: int = 2) -> Optional[List[Dict]]:
    text_to_analyze = f"岗位名称：{name}\n岗位描述：{description}\n技能要求：{skills}"

    if len(text_to_analyze.strip()) < 30:
        return []

    prompt = PROMPT_TEMPLATE.format(
        score_guide=SCORE_GUIDE,
        name=name[:200],
        description=description[:3500] if description else "",
        skills=skills if skills else ""
    )

    for attempt in range(retry):
        try:
            response = client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[
                    {"role": "system", "content": "你是招聘数据分析专家，只输出JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            skills_list = []
            for item in result.get("skills", []):
                name_skill = item.get("name", "").strip()
                score = item.get("score", 0)
                if name_skill and isinstance(score, (int, float)):
                    score = max(0.0, min(5.0, float(score)))
                    skills_list.append({"name": name_skill, "score": score})

            skills_list.sort(key=lambda x: x["score"], reverse=True)
            return skills_list

        except Exception as e:
            print(f"  尝试 {attempt+1}/{retry} 失败: {e}")
            if attempt < retry - 1:
                time.sleep(1)

    return []


def main():
    print("=" * 60)
    print("LLM 技能提取与标准化")
    print("=" * 60)

    with open('boss_jobs.json', 'r', encoding='utf-8') as f:
        jobs = json.load(f)

    print(f"共 {len(jobs)} 条岗位数据\n")

    normalized_jobs = []
    stats = {"success": 0, "failed": 0, "empty": 0}

    for idx, job in enumerate(jobs):
        name = job.get('name', '')
        description = job.get('description', '')
        original_skills = job.get('skills', '')

        print(f"[{idx+1}/{len(jobs)}] 处理中: {name[:35]}...")

        skills_normalized = extract_skills(name, description, original_skills)

        new_job = job.copy()

        if skills_normalized is not None:
            new_job['skills_normalized'] = skills_normalized

            if skills_normalized:
                stats["success"] += 1
                top = skills_normalized[0]
                print(f"    -> 提取到 {len(skills_normalized)} 个技能，最高: {top['name']}({top['score']})")
            else:
                stats["empty"] += 1
                print(f"    -> 未提取到技能")
        else:
            stats["failed"] += 1
            new_job['skills_normalized'] = []
            print(f"    -> 失败，跳过")

        normalized_jobs.append(new_job)
        time.sleep(0.5)

    output_file = 'boss_jobs_normalized.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(normalized_jobs, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"完成！输出: {output_file}")
    print(f"成功: {stats['success']}, 空: {stats['empty']}, 失败: {stats['failed']}")
    print("=" * 60)


if __name__ == "__main__":
    main()