import pandas as pd
import json
import time
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
import os
from collections import defaultdict, Counter

load_dotenv()

# ========== 配置 ==========
BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")

if not BASE_URL or not API_KEY:
    print("❌ 请在 .env 文件中配置 BASE_URL 和 API_KEY")
    exit(1)

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 评分标准
SCORE_GUIDE = """
评分标准（0.0-5.0分）：
- 0.0分：完全不要求，或明确说不需要
- 1.0分：仅作为加分项/优先项，不是必须
- 2.0分：一般了解/会用即可（如"了解""熟悉基础"）
- 3.0分：需要日常使用，能独立完成常规任务（如"熟练""独立开发"）
- 4.0分：深度掌握，能解决复杂问题（如"精通""深入""底层"）
- 5.0分：专家级别，能架构设计/攻坚难题（如"专家""架构""源码级"）
"""

PROMPT_TEMPLATE = """
你是招聘数据分析专家。请分析以下岗位描述，完成两个任务：

1. 提取所有提到的【技术技能】（不要提取软技能如沟通、团队协作）
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
- 同义技能合并（如"C"/"C语言"都写成"C"）
- 只提取技术相关技能，不包括软技能

岗位描述：
{description}
"""


def extract_skills_from_job(description: str, retry: int = 2) -> Optional[Dict[str, int]]:
    """从岗位描述中提取技能和分数"""
    if not isinstance(description, str) or len(description.strip()) < 20:
        return {}
    
    prompt = PROMPT_TEMPLATE.format(
        score_guide=SCORE_GUIDE,
        description=description[:3500]
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
            
            skills_dict = {}
            for item in result.get("skills", []):
                name = item.get("name", "").strip()
                score = item.get("score", 0)
                if name and isinstance(score, (int, float)):
                    skills_dict[name] = max(0.0, min(5.0, float(score)))
            
            return skills_dict
            
        except Exception as e:
            print(f"  ⚠️ 尝试 {attempt+1}/{retry} 失败: {e}")
            if attempt < retry - 1:
                time.sleep(1)
    
    return {}


def test_single_job():
    """测试单条数据"""
    print("=" * 60)
    print("🧪 测试模式")
    print("=" * 60)
    
    try:
        df = pd.read_csv('boss_jobs.csv', encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv('boss_jobs.csv', encoding='gbk')
    except FileNotFoundError:
        print("❌ 未找到 boss_jobs.csv")
        return False
    
    if len(df) == 0:
        return False
    
    first_row = df.iloc[0]
    test_text = (
        "岗位名称：" + str(first_row.get('name', '')) + "\n" +
        "岗位描述：" + str(first_row.get('description', '')) + "\n" +
        "技能要求：" + str(first_row.get('skills', ''))
    )
    
    print(f"\n📋 测试: {first_row.get('company', '未知')} - {first_row.get('name', '未知')}")
    print("⏳ 提取技能中...")
    
    skills = extract_skills_from_job(test_text)
    
    if skills:
        print("\n✅ 提取到的技能:")
        for skill, score in sorted(skills.items(), key=lambda x: x[1], reverse=True):
            bar = "█" * score + "░" * (5 - score)
            print(f"   {skill:<15} | {score}分 | {bar}")
        return True
    else:
        print("❌ 提取失败")
        return False


def main():
    print("=" * 60)
    print("🤖 LLM驱动的技能需求分析（自动提取技能）")
    print("=" * 60)
    
    # 测试
    if not test_single_job():
        print("\n❌ 测试失败，请检查配置")
        return
    
    print("\n" + "=" * 60)
    print("✅ 测试通过，开始批量分析...")
    print("=" * 60)
    
    # 读取数据
    try:
        df = pd.read_csv('boss_jobs.csv', encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv('boss_jobs.csv', encoding='gbk')
    except FileNotFoundError:
        print("❌ 未找到 boss_jobs.csv")
        return
    
    print(f"\n📊 共 {len(df)} 条岗位数据")
    
    # 准备分析文本
    df['text_to_analyze'] = (
        "岗位名称：" + df['name'].fillna('') + "\n" +
        "岗位描述：" + df['description'].fillna('') + "\n" +
        "技能要求：" + df['skills'].fillna('')
    )
    
    # 存储所有提取的技能
    all_skills = []  # 每条岗位的技能字典列表
    skill_stats = defaultdict(lambda: {'count': 0, 'scores': [], 'total_score': 0})
    
    print("\n🔍 正在分析每条岗位...\n")
    
    for idx, row in df.iterrows():
        company = str(row.get('company', '未知'))[:25]
        name = str(row.get('name', '未知'))[:30]
        print(f"  [{idx+1}/{len(df)}] {company} - {name}")
        
        skills = extract_skills_from_job(row['text_to_analyze'])
        all_skills.append(skills)
        
        if skills:
            for skill, score in skills.items():
                skill_stats[skill]['count'] += 1
                skill_stats[skill]['scores'].append(score)
                skill_stats[skill]['total_score'] += score
            
            top_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"      📌 {', '.join([f'{s}({sc})' for s, sc in top_skills])}")
        else:
            print(f"      ⚠️ 未提取到技能")
        
        time.sleep(0.3)
    
    # 统计结果
    print("\n" + "=" * 60)
    print("📊 【技能需求总排名】")
    print("=" * 60)
    
    # 计算每个技能的平均分和出现次数
    skill_summary = []
    for skill, stats in skill_stats.items():
        avg_score = stats['total_score'] / stats['count']
        skill_summary.append({
            'skill': skill,
            'count': stats['count'],
            'avg_score': avg_score,
            'total_score': stats['total_score']
        })
    
    skill_summary.sort(key=lambda x: x['total_score'], reverse=True)
    
    print(f"\n{'技能':<15} {'出现次数':<10} {'平均强度':<10} {'需求等级'}")
    print("-" * 50)
    
    for s in skill_summary[:15]:
        level = "🔥🔥🔥" if s['avg_score'] >= 3.5 else "🔥🔥" if s['avg_score'] >= 2.5 else "🔥"
        print(f"{s['skill']:<15} {s['count']:<10} {s['avg_score']:.2f}{'':<6} {level}")
    
    # 技能共现分析（哪些技能经常一起出现）
    print("\n" + "=" * 60)
    print("🔗 【技能共现分析】")
    print("=" * 60)
    
    co_occurrence = defaultdict(int)
    for skills in all_skills:
        skill_list = list(skills.keys())
        for i, s1 in enumerate(skill_list):
            for s2 in skill_list[i+1:]:
                key = tuple(sorted([s1, s2]))
                co_occurrence[key] += 1
    
    top_pairs = sorted(co_occurrence.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\n经常一起出现的技能组合：")
    for (s1, s2), count in top_pairs:
        print(f"  • {s1} + {s2} : {count} 个岗位")
    
    # TOP推荐岗位
    print("\n" + "=" * 60)
    print("🏆 【技能最丰富的TOP岗位】")
    print("=" * 60)
    
    # 计算每条岗位的技能丰富度（技能数量 * 平均强度）
    job_skill_score = []
    for idx, skills in enumerate(all_skills):
        if skills:
            score = sum(skills.values()) * len(skills)
            job_skill_score.append((idx, score, skills))
        else:
            job_skill_score.append((idx, 0, {}))
    
    job_skill_score.sort(key=lambda x: x[1], reverse=True)
    
    for rank, (idx, score, skills) in enumerate(job_skill_score[:5], 1):
        row = df.iloc[idx]
        print(f"\n{rank}. {row.get('company', '未知')}")
        print(f"   岗位: {row.get('name', '未知')}")
        print(f"   薪资: {row.get('salary', '未知')}")
        print(f"   技能丰富度: {score}")
        top_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)[:4]
        print(f"   技能要求: {', '.join([f'{s}({sc}★)' for s, sc in top_skills])}")
    
    # 学习建议
    print("\n" + "=" * 60)
    print("📚 【学习路径建议】")
    print("=" * 60)
    
    core_skills = [s for s in skill_summary if s['avg_score'] >= 2.5 and s['count'] >= 2]
    advanced_skills = [s for s in skill_summary if 1.5 <= s['avg_score'] < 2.5 and s['count'] >= 2]
    
    if core_skills:
        print("\n🔥 核心必备技能（市场需求大、强度高）:")
        for s in core_skills[:5]:
            print(f"   • {s['skill']}: 出现在 {s['count']} 个岗位，平均强度 {s['avg_score']:.1f}")
    
    if advanced_skills:
        print("\n📈 进阶加分技能（有区分度，建议学习）:")
        for s in advanced_skills[:5]:
            print(f"   • {s['skill']}: 出现在 {s['count']} 个岗位，平均强度 {s['avg_score']:.1f}")
    
    # 生成技能云数据
    print("\n" + "=" * 60)
    print("💡 【根据你的目标推荐】")
    print("=" * 60)
    
    # 找出要求较全面但门槛合理的岗位
    good_targets = []
    for idx, skills in enumerate(all_skills):
        if skills and len(skills) >= 3:
            avg_score = sum(skills.values()) / len(skills)
            if 2.0 <= avg_score <= 3.5:  # 要求适中
                good_targets.append((idx, skills))
    
    if good_targets:
        print("\n适合作为求职目标的岗位（要求全面但不苛刻）:")
        for idx, skills in good_targets[:3]:
            row = df.iloc[idx]
            skill_str = ', '.join(list(skills.keys())[:4])
            print(f"  • {row.get('company')} - {row.get('name')}")
            print(f"    核心技能: {skill_str}")
    
    # 保存结果
    # 将技能数据保存到Excel
    df['extracted_skills'] = [json.dumps(s, ensure_ascii=False) for s in all_skills]
    df['skill_count'] = [len(s) for s in all_skills]
    df['skill_total_score'] = [sum(s.values()) for s in all_skills]
    
    output_file = 'llm_skills_analysis.xlsx'
    df.to_excel(output_file, index=False)
    
    # 保存技能统计表
    skill_df = pd.DataFrame(skill_summary)
    skill_df.to_excel('skill_statistics.xlsx', index=False)
    
    print(f"\n💾 详细结果已保存:")
    print(f"   - {output_file}")
    print(f"   - skill_statistics.xlsx")
    
    print("\n" + "=" * 60)
    print("✅ 分析完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()