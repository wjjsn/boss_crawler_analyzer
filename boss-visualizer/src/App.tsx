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

  const isNodeConnected = useCallback((nodeId: string) => {
    if (!selectedNode) return false;
    if (!graphData) return false;
    if (nodeId === selectedNode) return true;
    return graphData.links.some(
      link => (link.source === selectedNode && link.target === nodeId) ||
              (link.target === selectedNode && link.source === nodeId)
    );
  }, [selectedNode, graphData]);

  const isLinkConnected = useCallback((source: string, target: string) => {
    if (!selectedNode) return false;
    return source === selectedNode || target === selectedNode;
  }, [selectedNode]);

  const getNodeStyle = useCallback((nodeId: string) => {
    const baseOpacity = !selectedNode ? 1 : (isNodeConnected(nodeId) ? 1 : 0.15);
    return {
      opacity: baseOpacity,
    };
  }, [selectedNode, isNodeConnected]);

  const hexToRgb = (hex: string) => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16),
    } : null;
  };

  const rgbToHex = (r: number, g: number, b: number) => {
    return '#' + [r, g, b].map(x => {
      const hex = Math.round(x).toString(16);
      return hex.length === 1 ? '0' + hex : hex;
    }).join('');
  };

  const hexToHsl = (hex: string) => {
    const rgb = hexToRgb(hex);
    if (!rgb) return null;
    const r = rgb.r / 255;
    const g = rgb.g / 255;
    const b = rgb.b / 255;

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h = 0, s = 0;
    const l = (max + min) / 2;

    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max) {
        case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
        case g: h = ((b - r) / d + 2) / 6; break;
        case b: h = ((r - g) / d + 4) / 6; break;
      }
    }

    return { h, s, l };
  };

  const hslToHex = (h: number, s: number, l: number) => {
    const hue2rgb = (p: number, q: number, t: number) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1/6) return p + (q - p) * 6 * t;
      if (t < 1/2) return q;
      if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
      return p;
    };

    let newR: number, newG: number, newB: number;
    if (s === 0) {
      newR = newG = newB = l;
    } else {
      const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
      const p = 2 * l - q;
      newR = hue2rgb(p, q, h + 1/3);
      newG = hue2rgb(p, q, h);
      newB = hue2rgb(p, q, h - 1/3);
    }

    return rgbToHex(newR * 255, newG * 255, newB * 255);
  };

  const adjustColor = (hex: string, intensity: number) => {
    const hsl = hexToHsl(hex);
    if (!hsl) return hex;

    const newS = Math.min(1, hsl.s + (1 - hsl.s) * intensity * 0.6);
    const newL = Math.max(0.12, hsl.l * (1 - intensity * 0.5));

    return hslToHex(hsl.h, newS, newL);
  };

  const getLinkColor = useCallback((source: string, target: string, value?: number) => {
    if (!graphData) return '#999';
    const sourceNode = graphData.nodes.find(n => n.id === source);
    const targetNode = graphData.nodes.find(n => n.id === target);
    if (!sourceNode || !targetNode) return '#999';

    const colorPairs: Record<string, Record<string, string>> = {
      skill: {
        skill: '#5470c6',
        job: '#91a7d4',
        company: '#a9b7d6',
        city: '#b8c5e2',
        salary: '#c5d0e8',
      },
      job: {
        skill: '#73c0de',
        job: '#73c0de',
        company: '#a8d8e8',
        city: '#bce6f0',
        salary: '#d0f0f5',
      },
      company: {
        skill: '#fac858',
        job: '#fdd36e',
        company: '#fac858',
        city: '#fde59a',
        salary: '#fef0c0',
      },
      city: {
        skill: '#95d475',
        job: '#a8e090',
        company: '#b8e8a8',
        city: '#95d475',
        salary: '#c0eab8',
      },
      salary: {
        skill: '#ee6666',
        job: '#f08888',
        company: '#f5a8a8',
        city: '#f8c0c0',
        salary: '#ee6666',
      },
    };

    let color = colorPairs[sourceNode.type]?.[targetNode.type] || '#999';

    if (value !== undefined && value > 0) {
      const maxValue = Math.max(...graphData.links.map(l => l.value));
      const intensity = Math.min(1, value / (maxValue || 1));
      color = adjustColor(color, intensity);
    }

    return color;
  }, [graphData]);

  const getLinkStyle = useCallback((source: string, target: string, value?: number) => {
    const baseOpacity = !selectedNode ? 0.6 : (isLinkConnected(source, target) ? 0.9 : 0.05);
    return {
      opacity: baseOpacity,
      color: getLinkColor(source, target, value),
    };
  }, [selectedNode, isLinkConnected, getLinkColor]);

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
              ...getNodeStyle(node.id),
            },
            label: {
              show: true,
              opacity: !selectedNode ? 1 : (isNodeConnected(node.id) ? 1 : 0.15),
            },
            emphasis: {
              itemStyle: {
                borderColor: '#333',
                borderWidth: 2,
                shadowBlur: 10,
                shadowColor: 'rgba(0,0,0,0.3)',
              },
              label: {
                show: true,
                opacity: !selectedNode ? 1 : (isNodeConnected(node.id) ? 1 : 0.15),
              },
            },
          })),
          links: graphData.links.map(link => ({
            source: link.source,
            target: link.target,
            lineStyle: {
              width: link.value,
              ...getLinkStyle(link.source, link.target, link.value),
            },
            emphasis: {
              lineStyle: {
                width: link.value + 1,
                opacity: !selectedNode ? 0.6 : (isLinkConnected(link.source, link.target) ? 0.9 : 0.05),
                color: getLinkColor(link.source, link.target, link.value),
              },
            },
          })),
          roam: true,
          label: {
            show: true,
            position: 'right',
            fontSize: 10,
          },
          force: {
            repulsion: 400,
            edgeLength: [60, 180],
          },
          lineStyle: {
            curveness: 0.1,
          },
        },
      ],
    };

    return option;
  }, [graphData, selectedNode, getNodeStyle, getLinkStyle]);

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

    const relatedByType = {
      skill: relatedNodes.filter((n: any) => n.type === 'skill'),
      job: relatedNodes.filter((n: any) => n.type === 'job'),
      company: relatedNodes.filter((n: any) => n.type === 'company'),
    };

    return {
      node,
      relatedNodes,
      relatedByType,
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
                  style={{ height: '800px', width: '100%' }}
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
                  style={{ height: '800px', width: '100%' }}
                />
              </div>
            )}
          </main>

          <aside className="info-panel">
            {selectedNodeInfo ? (
              <>
                <div className="node-detail">
                  <div className="node-header">
                    <span className={`node-type-badge ${selectedNodeInfo.node.type}`}>
                      {selectedNodeInfo.node.type === 'skill' ? '技能' :
                       selectedNodeInfo.node.type === 'job' ? '岗位' : '公司'}
                    </span>
                    <h3>{selectedNodeInfo.node.name}</h3>
                  </div>
                  <div className="node-stats">
                    <div className="stat-item">
                      <span className="stat-label">平均薪资</span>
                      <span className="stat-value">{selectedNodeInfo.avgSalary || 'N/A'}元/天</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-label">出现次数</span>
                      <span className="stat-value">{selectedNodeInfo.count}</span>
                    </div>
                  </div>
                </div>

                <div className="related-section">
                  <div className="related-column jobs-column">
                    <h4>相关岗位</h4>
                    <div className="related-list">
                      {selectedNodeInfo.relatedByType.job?.length > 0 ? (
                        selectedNodeInfo.relatedByType.job.map((n: any) => (
                          <button
                            key={n.id}
                            className="related-item"
                            onClick={() => setSelectedNode(n.id)}
                          >
                            <span className="item-name">{n.name}</span>
                            <span className="item-count">{n.value}次</span>
                          </button>
                        ))
                      ) : (
                        <p className="no-data">无关联岗位</p>
                      )}
                    </div>
                  </div>

                  <div className="related-column companies-column">
                    <h4>相关公司</h4>
                    <div className="related-list">
                      {selectedNodeInfo.relatedByType.company?.length > 0 ? (
                        selectedNodeInfo.relatedByType.company.map((n: any) => (
                          <button
                            key={n.id}
                            className="related-item"
                            onClick={() => setSelectedNode(n.id)}
                          >
                            <span className="item-name">{n.name}</span>
                            <span className="item-count">{n.value}次</span>
                          </button>
                        ))
                      ) : (
                        <p className="no-data">无关联公司</p>
                      )}
                    </div>
                  </div>
                </div>

                <div className="related-section skills-section">
                  <h4>相关技能</h4>
                  <div className="related-list skills-list">
                    {selectedNodeInfo.relatedByType.skill?.length > 0 ? (
                      selectedNodeInfo.relatedByType.skill.map((n: any) => (
                        <button
                          key={n.id}
                          className="related-item skill-item"
                          onClick={() => setSelectedNode(n.id)}
                        >
                          <span className="item-name">{n.name}</span>
                          <span className="item-count">{n.value}次</span>
                        </button>
                      ))
                    ) : (
                      <p className="no-data">无关联技能</p>
                    )}
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