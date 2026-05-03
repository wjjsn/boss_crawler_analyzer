export interface Job {
  name: string;
  salary: string;
  experience: string;
  degree: string;
  city: string;
  district: string;
  description: string;
  skills: string;
  welfare: string;
  boss_name: string;
  boss_title: string;
  active_time: string;
  company: string;
  industry: string;
  scale: string;
  stage: string;
  address: string;
  url: string;
}

export interface GraphNode {
  id: string;
  name: string;
  type: 'skill' | 'job' | 'company' | 'city' | 'salary';
  value?: number;
  avgSalary?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  value: number;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface FilterState {
  cities: string[];
  industries: string[];
  salaryRange: [number, number];
  degrees: string[];
}

export interface SkillCooccurrence {
  skillA: string;
  skillB: string;
  count: number;
}

export interface JobPath {
  name: string;
  skills: string[];
  avgSalary: number;
  count: number;
}