import { useState, useCallback, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import type { Job, GraphData, FilterState, SkillCooccurrence } from './types';
import {
  transformToGraphData,
  getSkillCooccurrence,
  getUniqueValues,
  getSalaryRange,
} from './dataProcessor';
import './App.css';

function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [cooccurrence, setCooccurrence] = useState<SkillCooccurrence[]>([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'graph' | 'heatmap'>('graph');

  const [filters, setFilters] = useState<FilterState>({
    cities: [],
    industries: [],
    salaryRange: [0, 500],
    degrees: [],
  });

  const cities = useMemo(() => getUniqueValues(jobs, 'city'), [jobs]);
  const industries = useMemo(() => getUniqueValues(jobs, 'industry'), [jobs]);
  const degrees = useMemo(() => getUniqueValues(jobs, 'degree'), [jobs]);
  const salaryRange = useMemo(() => getSalaryRange(jobs), [jobs]);

  const handleFileLoad = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = JSON.parse(e.target?.result as string);
        setJobs(data);

        const initialFilters: FilterState = {
          cities: [],
          industries: [],
          salaryRange: getSalaryRange(data),
          degrees: [],
        };
        setFilters(initialFilters);

        const graph = transformToGraphData(data, initialFilters);
        setGraphData(graph);

        const cooc = getSkillCooccurrence(data, initialFilters);
        setCooccurrence(cooc);
      } catch (err) {
        console.error('Failed to parse JSON:', err);
      }
    };
    reader.readAsText(file);
  }, []);

  const handleFilterChange = useCallback((newFilters: FilterState) => {
    setFilters(newFilters);
    if (jobs.length > 0) {
      const graph = transformToGraphData(jobs, newFilters);
      setGraphData(graph);
      const cooc = getSkillCooccurrence(jobs, newFilters);
      setCooccurrence(cooc);
    }
    setSelectedNode(null);
  }, [jobs]);

  const graphOption = useMemo((): EChartsOption => {
    if (!graphData || graphData.nodes.length === 0) {
      return {};
    }

    const nodeColors: Record<string, string> = {
      skill: '#5470c6',
      job: '#73c0de',
      company: '#fac858',
      city: '#95d475',
      salary: '#ee6666',
    };

    const categoryData = [
      { name: '技能', icon: 'circle' },
      { name: '岗位', icon: 'circle' },
      { name: '公司', icon: 'circle' },
    ];

    const option: EChartsOption = {
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.dataType === 'edge') {
            return `${params.data.source} → ${params.data.target}`;
          }
          const node = params.data;
          return `${node.name}<br/>平均薪资: ${node.avgSalary || 'N/A'}<br/>出现次数: ${node.value || 1}`;
        },
      },
      legend: [
        {
          data: categoryData.map(c => c.name),
          top: 20,
        },
      ],
      series: [
        {
          type: 'graph',
          layout: 'force',
          symbolSize: (val: number) => Math.max(20, Math.min(60, val * 5)),
          categories: categoryData,
          data: graphData.nodes.map(node => ({
            id: node.id,
            name: node.name,
            value: node.value,
            avgSalary: node.avgSalary,
            category: node.type === 'skill' ? 0 : node.type === 'job' ? 1 : 2,
            itemStyle: {
              color: nodeColors[node.type] || '#999',
            },
          })),
          links: graphData.links.map(link => ({
            source: link.source,
            target: link.target,
            lineStyle: {
              width: link.value,
              opacity: 0.6,
            },
          })),
          roam: true,
          label: {
            show: true,
            position: 'right',
            fontSize: 10,
          },
          force: {
            repulsion: 100,
            edgeLength: [50, 200],
          },
          lineStyle: {
            curveness: 0.1,
          },
        },
      ],
    };

    return option;
  }, [graphData]);

  const heatmapOption = useMemo((): EChartsOption => {
    if (cooccurrence.length === 0) {
      return {};
    }

    const skills = Array.from(
      new Set(cooccurrence.flatMap(c => [c.skillA, c.skillB]))
    ).slice(0, 30);

    const matrix: [number, number, number][] = [];
    cooccurrence.forEach(c => {
      const i = skills.indexOf(c.skillA);
      const j = skills.indexOf(c.skillB);
      if (i >= 0 && j >= 0) {
        matrix.push([i, j, c.count]);
        matrix.push([j, i, c.count]);
      }
    });

    return {
      tooltip: {
        formatter: (params: any) => {
          return `${skills[params.value[0]]} & ${skills[params.value[1]]}: ${params.value[2]}次`;
        },
      },
      grid: {
        left: 120,
        right: 120,
        top: 60,
        bottom: 60,
      },
      xAxis: {
        type: 'category',
        data: skills,
        splitArea: { show: true },
        axisLabel: { rotate: 45, fontSize: 9 },
      },
      yAxis: {
        type: 'category',
        data: skills,
        splitArea: { show: true },
        axisLabel: { fontSize: 9 },
      },
      visualMap: {
        min: 0,
        max: Math.max(...cooccurrence.map(c => c.count)),
        calculable: true,
        left: 'right',
        top: 'center',
      },
      series: [
        {
          type: 'heatmap',
          data: matrix,
          label: {
            show: false,
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    };
  }, [cooccurrence]);

  const selectedNodeInfo = useMemo(() => {
    if (!selectedNode || !graphData) return null;
    const node = graphData.nodes.find(n => n.id === selectedNode);
    if (!node) return null;

    const relatedLinks = graphData.links.filter(
      l => l.source === selectedNode || l.target === selectedNode
    );
    const relatedNodes = relatedLinks.map(l => {
      const targetId = l.source === selectedNode ? l.target : l.source;
      return graphData.nodes.find(n => n.id === targetId);
    }).filter(Boolean);

    return {
      node,
      relatedNodes,
      avgSalary: node.avgSalary,
      count: node.value,
    };
  }, [selectedNode, graphData]);

  const toggleFilter = useCallback((
    field: 'cities' | 'industries' | 'degrees',
    value: string
  ) => {
    setFilters(prev => {
      const current = prev[field];
      const newValues = current.includes(value)
        ? current.filter(v => v !== value)
        : [...current, value];
      return { ...prev, [field]: newValues };
    });
  }, []);

  return (
    <div className="app">
      {!jobs.length ? (
        <div className="upload-section">
          <label className="upload-button">
            <input
              type="file"
              accept=".json"
              onChange={handleFileLoad}
              style={{ display: 'none' }}
            />
            从本地加载 JSON 文件
          </label>
        </div>
      ) : (
        <div className="main-content">
          <aside className="sidebar">
            <h3>筛选器</h3>

            <div className="filter-group">
              <h4>城市</h4>
              <div className="filter-tags">
                {cities.map(city => (
                  <button
                    key={city}
                    className={`tag ${filters.cities.includes(city) ? 'active' : ''}`}
                    onClick={() => toggleFilter('cities', city)}
                  >
                    {city}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-group">
              <h4>行业</h4>
              <div className="filter-tags">
                {industries.map(ind => (
                  <button
                    key={ind}
                    className={`tag ${filters.industries.includes(ind) ? 'active' : ''}`}
                    onClick={() => toggleFilter('industries', ind)}
                  >
                    {ind}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-group">
              <h4>学历</h4>
              <div className="filter-tags">
                {degrees.map(deg => (
                  <button
                    key={deg}
                    className={`tag ${filters.degrees.includes(deg) ? 'active' : ''}`}
                    onClick={() => toggleFilter('degrees', deg)}
                  >
                    {deg}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-group">
              <h4>薪资范围</h4>
              <div className="salary-range">
                <span>{filters.salaryRange[0]}元/天</span>
                <input
                  type="range"
                  min={salaryRange[0]}
                  max={salaryRange[1]}
                  value={filters.salaryRange[1]}
                  onChange={e => setFilters(prev => ({
                    ...prev,
                    salaryRange: [prev.salaryRange[0], parseInt(e.target.value)],
                  }))}
                />
                <span>{filters.salaryRange[1]}元/天</span>
              </div>
            </div>

            <button
              className="apply-button"
              onClick={() => handleFilterChange(filters)}
            >
              应用筛选
            </button>
          </aside>

          <main className="content">
            <div className="tabs">
              <button
                className={`tab ${activeTab === 'graph' ? 'active' : ''}`}
                onClick={() => setActiveTab('graph')}
              >
                关系图谱
              </button>
              <button
                className={`tab ${activeTab === 'heatmap' ? 'active' : ''}`}
                onClick={() => setActiveTab('heatmap')}
              >
                技能关联矩阵
              </button>
            </div>

            {activeTab === 'graph' ? (
              <div className="chart-container">
                <ReactECharts
                  option={graphOption}
                  style={{ height: '600px', width: '100%' }}
                  onEvents={{
                    click: (params: any) => {
                      if (params.dataType === 'node') {
                        setSelectedNode(params.data.id);
                      }
                    },
                  }}
                />
              </div>
            ) : (
              <div className="chart-container">
                <ReactECharts
                  option={heatmapOption}
                  style={{ height: '600px', width: '100%' }}
                />
              </div>
            )}
          </main>

          <aside className="info-panel">
            {selectedNodeInfo ? (
              <>
                <h3>{selectedNodeInfo.node.name}</h3>
                <div className="info-item">
                  <span className="label">类型:</span>
                  <span className="value">{selectedNodeInfo.node.type}</span>
                </div>
                <div className="info-item">
                  <span className="label">平均薪资:</span>
                  <span className="value">{selectedNodeInfo.avgSalary || 'N/A'}元/天</span>
                </div>
                <div className="info-item">
                  <span className="label">出现次数:</span>
                  <span className="value">{selectedNodeInfo.count}</span>
                </div>
                <div className="info-item">
                  <span className="label">关联节点:</span>
                  <div className="related-nodes">
                    {selectedNodeInfo.relatedNodes?.map((n: any) => (
                      <span key={n.id} className="related-tag">
                        {n.name}
                      </span>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="placeholder">
                <p>点击图中的节点查看详情</p>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

export default App;