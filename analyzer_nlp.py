import pandas as pd
import re
import jieba
from collections import defaultdict
import warnings
from tqdm import tqdm
warnings.filterwarnings('ignore')

# ========== 配置部分 ==========
# 要分析的技能列表
SKILLS = ['C', 'C++', 'Python', 'STM32', 'RTOS', 'Linux', 'ARM', 
          'BLE', '蓝牙', 'I2C', 'SPI', 'UART', 'PCB', '嵌入式', 
          '驱动', '传感器', 'FreeRTOS', 'Zephyr', 'AI', '机器学习']

# 强度词词典（带权重）
STRENGTH_WORDS = {
    5: ['精通', '深入', '底层', '内核', '源码级', '专家', '架构'],
    4: ['熟练掌握', '独立开发', '扎实', '项目经验', '实际项目', '主导'],
    3: ['熟悉', '掌握', '了解', '会用', '使用过', '有基础'],
    2: ['优先', '加分', '有经验', '经历者优先', '更佳'],
    1: ['接触过', '了解一点', '听说过', '初步了解']
}

# 否定词（出现则强度归零）
NEGATION_WORDS = ['不', '没', '无需', '不需要', '非', '勿需', '不需要有']

# 岗位类型关键词映射
JOB_TYPES = {
    '纯软件嵌入式': ['嵌入式软件', '软件工程', '应用开发', '上层应用', 'UI', 'APP'],
    '软硬结合': ['硬件', 'PCB', '电路', '驱动开发', '单片机', 'STM32', 'ARM'],
    '算法/AI': ['算法', 'AI', '智能', 'VSLAM', 'SLAM', '视觉', '机器学习', '深度学习'],
    '底层/驱动': ['驱动', 'BSP', '内核', 'Linux底层', 'bootloader'],
    '通信/协议': ['蓝牙', 'BLE', 'WiFi', '协议', '网络', 'TCP/IP', '流媒体']
}

# ========== 核心函数 ==========

def extract_skill_strength(text, skill):
    """
    提取单个技能在文本中的需求强度（0-5）
    使用：正则匹配 + 距离约束 + 否定词检测
    """
    if not isinstance(text, str):
        return 0
    
    # 转小写用于匹配（但保留中文）
    text_lower = text.lower()
    skill_lower = skill.lower()
    
    # 技能词的正则（支持中英文）
    # 注意：C++ 需要特殊处理
    if skill == 'C++':
        skill_pattern = r'C\+\+'
    elif skill == 'C':
        # 避免匹配到 C++ 或 Python 中的 C
        skill_pattern = r'\bC\b'
    else:
        skill_pattern = skill
    
    # 在文本中查找技能词的位置
    matches = []
    for match in re.finditer(skill_pattern, text, re.IGNORECASE):
        # 获取技能词前后30个字符的上下文
        start = max(0, match.start() - 40)
        end = min(len(text), match.end() + 40)
        context = text[start:end]
        matches.append({
            'position': match.start(),
            'context': context,
            'full_context': text[max(0, match.start()-80):min(len(text), match.end()+80)]
        })
    
    if not matches:
        return 0
    
    max_strength = 0
    
    for match_data in matches:
        context = match_data['context']
        
        # 1. 检查否定词（如果上下文中有否定词，跳过这个匹配）
        has_negation = False
        for neg in NEGATION_WORDS:
            if neg in context[:30]:  # 只在技能词前30字内检查
                has_negation = True
                break
        
        if has_negation:
            continue
        
        # 2. 匹配强度词
        for strength, words in STRENGTH_WORDS.items():
            for word in words:
                if word in context:
                    max_strength = max(max_strength, strength)
                    break
            
            # 如果有修饰词同时出现，强度可以+1（但不能超过5）
            # 例如："非常熟悉" -> 基础3 + 1 = 4
            if max_strength > 0 and any(adv in context for adv in ['非常', '尤其', '特别', '极其']):
                max_strength = min(5, max_strength + 1)
    
    return max_strength


def extract_all_skills(text):
    """提取文本中所有技能及其强度"""
    if not isinstance(text, str):
        return {}, 0
    
    # 合并 description 和 skills 列
    combined_text = text
    
    results = {}
    max_strength_overall = 0
    
    for skill in SKILLS:
        strength = extract_skill_strength(combined_text, skill)
        if strength > 0:
            results[skill] = strength
            max_strength_overall = max(max_strength_overall, strength)
    
    return results, max_strength_overall


def classify_job_type(description):
    """根据描述分类岗位类型"""
    if not isinstance(description, str):
        return '未知'
    
    scores = defaultdict(int)
    for job_type, keywords in JOB_TYPES.items():
        for keyword in keywords:
            if keyword.lower() in description.lower():
                scores[job_type] += 1
    
    if not scores:
        return '通用嵌入式'
    
    return max(scores, key=scores.get)


def calculate_job_score(row):
    """
    计算岗位综合得分（用于推荐）
    """
    score = 0
    
    # 1. 薪资得分（元/天）
    salary = row.get('salary', '')
    salary_score = 0
    if isinstance(salary, str):
        numbers = re.findall(r'(\d+)', salary)
        if len(numbers) >= 2:
            avg_salary = (int(numbers[0]) + int(numbers[1])) / 2
            salary_score = min(10, avg_salary / 50)  # 250元/天 = 5分，500元/天 = 10分
        elif len(numbers) == 1:
            salary_score = min(10, int(numbers[0]) / 50)
    score += salary_score * 0.3  # 薪资权重30%
    
    # 2. 技能匹配度得分
    if 'skills_parsed' in row and isinstance(row['skills_parsed'], dict):
        # 技能强度越高越好
        skill_scores = sum(row['skills_parsed'].values()) / max(1, len(row['skills_parsed']))
        score += skill_scores * 2  # 技能权重较高
    
    # 3. 公司规模得分
    scale = row.get('scale', '')
    if isinstance(scale, str):
        if '10000' in scale:
            score += 10
        elif '1000' in scale:
            score += 8
        elif '100' in scale:
            score += 5
        elif '20' in scale:
            score += 3
        else:
            score += 1
    
    # 4. 转正机会得分
    desc = row.get('description', '')
    if isinstance(desc, str):
        if any(kw in desc for kw in ['转正', '留用', '校招', '正式员工', '股份激励']):
            score += 5
    
    return round(score, 2)


# ========== 主程序 ==========

def main():
    print("=" * 60)
    print("嵌入式实习岗位智能分析系统")
    print("=" * 60)
    
    # 1. 读取数据
    try:
        df = pd.read_csv('boss_jobs.csv', encoding='utf-8')
        print(f"\n✅ 成功读取 {len(df)} 条岗位数据")
    except UnicodeDecodeError:
        # 尝试其他编码
        df = pd.read_csv('boss_jobs.csv', encoding='gbk')
        print(f"\n✅ 成功读取 {len(df)} 条岗位数据 (GBK编码)")
    except FileNotFoundError:
        print("\n❌ 未找到 boss_jobs.csv 文件！")
        print("请确保文件在当前目录下")
        return
    
    # 2. 数据预处理
    print("\n📊 数据预处理中...")
    
    # 合并文本列用于分析
    df['combined_text'] = df['description'].fillna('') + ' ' + df['skills'].fillna('')
    
    # 3. 提取技能强度
    print("🔍 提取技能需求强度...")
    results = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="提取技能"):
        skills, max_strength = extract_all_skills(row['combined_text'])
        results.append((skills, max_strength))
    df['skills_parsed'], df['max_strength'] = zip(*results)
    
    # 4. 岗位分类
    print("🏷️ 岗位类型分类...")
    df['job_type'] = df['description'].apply(classify_job_type)
    
    # 5. 计算综合得分
    print("⭐ 计算岗位推荐得分...")
    df['recommend_score'] = df.apply(calculate_job_score, axis=1)
    
    # ========== 分析结果 ==========
    
    print("\n" + "=" * 60)
    print("【技能需求强度排名】")
    print("=" * 60)
    
    # 统计所有技能的出现频率和平均强度
    skill_stats = defaultdict(lambda: {'count': 0, 'total_strength': 0, 'strengths': []})
    
    for skills in tqdm(df['skills_parsed'], desc="统计技能"):
        for skill, strength in skills.items():
            skill_stats[skill]['count'] += 1
            skill_stats[skill]['total_strength'] += strength
            skill_stats[skill]['strengths'].append(strength)
    
    # 排序并输出
    top_skills = sorted(skill_stats.items(), 
                       key=lambda x: x[1]['total_strength'], 
                       reverse=True)
    
    print(f"\n{'技能':<15} {'出现次数':<10} {'平均强度':<10} {'强度分布':<20}")
    print("-" * 60)
    for skill, stats in top_skills[:15]:
        avg_strength = stats['total_strength'] / stats['count']
        # 显示强度分布（1-5分的比例）
        dist = f"1★:{stats['strengths'].count(1)} 2★:{stats['strengths'].count(2)} 3★:{stats['strengths'].count(3)} 4★:{stats['strengths'].count(4)} 5★:{stats['strengths'].count(5)}"
        print(f"{skill:<15} {stats['count']:<10} {avg_strength:.2f}{'':<6} {dist[:30]}")
    
    # ========== 岗位类型分布 ==========
    print("\n" + "=" * 60)
    print("【岗位类型分布】")
    print("=" * 60)
    type_counts = df['job_type'].value_counts()
    for job_type, count in type_counts.items():
        avg_score = df[df['job_type'] == job_type]['recommend_score'].mean()
        print(f"{job_type:<15}: {count:>3} 个岗位 (平均推荐分: {avg_score:.1f})")
    
    # ========== TOP推荐岗位 ==========
    print("\n" + "=" * 60)
    print("【TOP 5 推荐岗位】")
    print("=" * 60)
    
    top_jobs = df.nlargest(5, 'recommend_score')
    for idx, row in top_jobs.iterrows():
        print(f"\n🏆 第 {list(top_jobs.index).index(idx) + 1} 名")
        print(f"   公司: {row.get('company', '未知')}")
        print(f"   岗位: {row.get('name', '未知')}")
        print(f"   薪资: {row.get('salary', '未知')}")
        print(f"   推荐分: {row['recommend_score']}")
        print(f"   岗位类型: {row['job_type']}")
        if isinstance(row['skills_parsed'], dict) and row['skills_parsed']:
            top_skills_in_job = sorted(row['skills_parsed'].items(), key=lambda x: x[1], reverse=True)[:3]
            print(f"   核心技能: {', '.join([f'{s}({st}★)' for s, st in top_skills_in_job])}")
    
    # ========== 学习建议 ==========
    print("\n" + "=" * 60)
    print("【学习路径建议】")
    print("=" * 60)
    
    # 基于技能统计生成建议
    must_have = []
    nice_to_have = []
    
    for skill, stats in top_skills[:10]:
        avg_strength = stats['total_strength'] / stats['count']
        if avg_strength >= 3.5 and stats['count'] >= 3:
            must_have.append(skill)
        elif avg_strength >= 2.0:
            nice_to_have.append(skill)
    
    print("\n🔥 必须掌握的核心技能:")
    for skill in must_have[:5]:
        print(f"   • {skill}")
    
    print("\n📈 建议学习的进阶技能:")
    for skill in nice_to_have[:8]:
        if skill not in must_have:
            print(f"   • {skill}")
    
    # ========== 保存结果 ==========
    output_file = 'analysis_result.xlsx'
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # 保存详细数据
        df.to_excel(writer, sheet_name='原始数据', index=False)
        
        # 保存技能统计
        skill_df = pd.DataFrame([{
            '技能': s,
            '出现次数': stats['count'],
            '平均强度': stats['total_strength'] / stats['count'],
            '总强度': stats['total_strength']
        } for s, stats in skill_stats.items()])
        skill_df = skill_df.sort_values('总强度', ascending=False)
        skill_df.to_excel(writer, sheet_name='技能统计', index=False)
    
    print(f"\n✅ 详细分析结果已保存至: {output_file}")
    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
