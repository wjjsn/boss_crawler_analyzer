import type { Job, GraphData, GraphNode, GraphLink, FilterState, SkillCooccurrence } from './types';

export function parseSalary(salary: string): number {
  const match = salary.match(/(\d+)-(\d+)/);
  if (match) {
    return (parseInt(match[1]) + parseInt(match[2])) / 2;
  }
  const single = salary.match(/(\d+)/);
  return single ? parseInt(single[1]) : 0;
}

export function parseScale(scale: string): number {
  const match = scale.match(/(\d+)-(\d+)/);
  if (match) {
    return (parseInt(match[1]) + parseInt(match[2])) / 2;
  }
  if (scale.includes('10000')) return 10000;
  if (scale.includes('0')) return 10;
  return 50;
}

export function transformToGraphData(jobs: Job[], filters: FilterState): GraphData {
  const filteredJobs = jobs.filter(job => {
    if (filters.cities.length > 0 && !filters.cities.includes(job.city)) return false;
    if (filters.industries.length > 0 && !filters.industries.includes(job.industry)) return false;
    const salary = parseSalary(job.salary);
    if (salary < filters.salaryRange[0] || salary > filters.salaryRange[1]) return false;
    if (filters.degrees.length > 0 && !filters.degrees.includes(job.degree)) return false;
    return true;
  });

  const nodes: GraphNode[] = [];
  const links: GraphLink[] = [];
  const nodeMap = new Map<string, GraphNode>();

  const jobSalaryMap = new Map<string, { total: number; count: number }>();
  const skillJobMap = new Map<string, Map<string, number>>();
  const skillSalaryMap = new Map<string, { total: number; count: number }>();
  const companyJobMap = new Map<string, Map<string, number>>();

  filteredJobs.forEach(job => {
    const salary = parseSalary(job.salary);
    const jobKey = job.name;
    const companyKey = job.company;
    const skills = job.skills ? job.skills.split(',').map(s => s.trim()).filter(Boolean) : [];

    if (!jobSalaryMap.has(jobKey)) {
      jobSalaryMap.set(jobKey, { total: 0, count: 0 });
    }
    const js = jobSalaryMap.get(jobKey)!;
    js.total += salary;
    js.count += 1;

    if (!companyJobMap.has(companyKey)) {
      companyJobMap.set(companyKey, new Map());
    }
    const cjm = companyJobMap.get(companyKey)!;
    cjm.set(jobKey, (cjm.get(jobKey) || 0) + 1);

    skills.forEach(skill => {
      if (!skillJobMap.has(skill)) {
        skillJobMap.set(skill, new Map());
      }
      const sjm = skillJobMap.get(skill)!;
      sjm.set(jobKey, (sjm.get(jobKey) || 0) + 1);

      if (!skillSalaryMap.has(skill)) {
        skillSalaryMap.set(skill, { total: 0, count: 0 });
      }
      const ssm = skillSalaryMap.get(skill)!;
      ssm.total += salary;
      ssm.count += 1;
    });
  });

  jobSalaryMap.forEach((data, jobName) => {
    const node: GraphNode = {
      id: `job_${jobName}`,
      name: jobName,
      type: 'job',
      value: data.count,
      avgSalary: Math.round(data.total / data.count),
    };
    nodeMap.set(`job_${jobName}`, node);
    nodes.push(node);
  });

  skillJobMap.forEach((_, skill) => {
    const ssm = skillSalaryMap.get(skill)!;
    const node: GraphNode = {
      id: `skill_${skill}`,
      name: skill,
      type: 'skill',
      value: skillJobMap.get(skill)!.size,
      avgSalary: Math.round(ssm.total / ssm.count),
    };
    nodeMap.set(`skill_${skill}`, node);
    nodes.push(node);
  });

  companyJobMap.forEach((_, company) => {
    const node: GraphNode = {
      id: `company_${company}`,
      name: company,
      type: 'company',
      value: companyJobMap.get(company)!.size,
    };
    nodeMap.set(`company_${company}`, node);
    nodes.push(node);
  });

  skillJobMap.forEach((jobMap, skill) => {
    jobMap.forEach((count, jobName) => {
      links.push({
        source: `skill_${skill}`,
        target: `job_${jobName}`,
        value: count,
      });
    });
  });

  companyJobMap.forEach((jobMap, company) => {
    jobMap.forEach((count, jobName) => {
      links.push({
        source: `company_${company}`,
        target: `job_${jobName}`,
        value: count,
      });
    });
  });

  return { nodes, links };
}

export function getSkillCooccurrence(jobs: Job[], filters: FilterState): SkillCooccurrence[] {
  const filteredJobs = jobs.filter(job => {
    if (filters.cities.length > 0 && !filters.cities.includes(job.city)) return false;
    if (filters.industries.length > 0 && !filters.industries.includes(job.industry)) return false;
    const salary = parseSalary(job.salary);
    if (salary < filters.salaryRange[0] || salary > filters.salaryRange[1]) return false;
    if (filters.degrees.length > 0 && !filters.degrees.includes(job.degree)) return false;
    return true;
  });

  const cooccurrence: Map<string, number> = new Map();

  filteredJobs.forEach(job => {
    const skills = job.skills ? job.skills.split(',').map(s => s.trim()).filter(Boolean) : [];
    for (let i = 0; i < skills.length; i++) {
      for (let j = i + 1; j < skills.length; j++) {
        const key = [skills[i], skills[j]].sort().join('|||');
        cooccurrence.set(key, (cooccurrence.get(key) || 0) + 1);
      }
    }
  });

  return Array.from(cooccurrence.entries()).map(([key, count]) => {
    const [skillA, skillB] = key.split('|||');
    return { skillA, skillB, count };
  }).filter(c => c.count >= 3).sort((a, b) => b.count - a.count);
}

export function getUniqueValues(jobs: Job[], field: keyof Job): string[] {
  const values = new Set<string>();
  jobs.forEach(job => {
    const val = job[field];
    if (val) values.add(val);
  });
  return Array.from(values).sort();
}

export function getSalaryRange(jobs: Job[]): [number, number] {
  let min = Infinity;
  let max = 0;
  jobs.forEach(job => {
    const salary = parseSalary(job.salary);
    if (salary < min) min = salary;
    if (salary > max) max = salary;
  });
  return [min === Infinity ? 0 : min, max];
}