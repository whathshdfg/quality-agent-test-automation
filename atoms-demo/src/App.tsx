import { NavLink, Route, Routes, useNavigate, useParams } from 'react-router-dom';
import { BarChart3, BookOpen, FilePlus2, FlaskConical, History, Info, LayoutDashboard, Menu, Plus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { QualityTask, TaskDraft, TestCase } from './types';
import { businessTypes, examples, riskTagOptions } from './data/examples';
import { useTasks } from './hooks/useTasks';
import { exportJson, exportMarkdown } from './utils/exporters';
import { supplementAllGaps, supplementForGap } from './features/supplement';
import { buildCaseFromPoint } from './features/caseGenerator';
import { makeId } from './utils/id';

function App() {
  const taskApi = useTasks();
  const [navOpen, setNavOpen] = useState(false);
  return (
    <div className="shell">
      <aside className={`sidebar ${navOpen ? 'open' : ''}`}>
        <div className="brand"><FlaskConical size={26} /><div><strong>Quality Agent Studio</strong><span>需求驱动的智能测试工作台</span></div></div>
        <nav>
          <NavLink to="/"><LayoutDashboard size={18} />工作台</NavLink>
          <NavLink to="/history"><History size={18} />历史任务</NavLink>
          <NavLink to="/examples"><BookOpen size={18} />示例需求</NavLink>
          <NavLink to="/about"><Info size={18} />产品说明</NavLink>
        </nav>
        <p className="storage-note">数据保存在当前浏览器</p>
      </aside>
      <main className="main">
        <button className="mobile-menu" onClick={() => setNavOpen(!navOpen)} aria-label="切换导航"><Menu size={18} /></button>
        <Routes>
          <Route path="/" element={<Dashboard {...taskApi} />} />
          <Route path="/new" element={<NewTask addTask={taskApi.addTask} />} />
          <Route path="/history" element={<HistoryPage tasks={taskApi.tasks} deleteTask={taskApi.deleteTask} />} />
          <Route path="/examples" element={<ExamplesPage addTask={taskApi.addTask} />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/task/:id" element={<TaskDetail tasks={taskApi.tasks} updateTask={taskApi.updateTask} deleteTask={taskApi.deleteTask} autosave={taskApi.message} />} />
        </Routes>
      </main>
    </div>
  );
}

function PageHeader({ title, desc, action }: { title: string; desc: string; action?: React.ReactNode }) {
  return <header className="page-header"><div><h1>{title}</h1><p>{desc}</p></div>{action}</header>;
}

function Dashboard({ tasks, stats, deleteTask }: ReturnType<typeof useTasks>) {
  const navigate = useNavigate();
  const recent = tasks.slice(0, 6);
  return (
    <>
      <PageHeader title="工作台" desc="从自然语言需求生成规则、测试点、用例和覆盖缺口。" action={<button onClick={() => navigate('/new')}><Plus size={18} />新建测试任务</button>} />
      <section className="stats">
        <Metric icon={<BarChart3 />} label="任务总数" value={stats.taskCount} />
        <Metric icon={<FlaskConical />} label="测试用例总数" value={stats.caseCount} />
        <Metric icon={<LayoutDashboard />} label="平均覆盖率" value={`${stats.average}%`} />
        <Metric icon={<Info />} label="P0 高优先级" value={stats.p0Count} />
      </section>
      {tasks.length === 0 ? <EmptyState /> : <TaskList tasks={recent} deleteTask={deleteTask} />}
    </>
  );
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return <div className="metric"><span>{icon}</span><small>{label}</small><strong>{value}</strong></div>;
}

function EmptyState() {
  const navigate = useNavigate();
  return (
    <section className="empty">
      <h2>把业务需求变成可评审的测试资产</h2>
      <p>当前演示版使用本地可解释规则引擎生成测试建议，无需上传业务需求，也不依赖外部模型 API。</p>
      <div className="actions"><button onClick={() => navigate('/new')}><FilePlus2 size={18} />新建任务</button><button className="secondary" onClick={() => navigate('/examples')}>加载示例任务</button></div>
    </section>
  );
}

function TaskList({ tasks, deleteTask }: { tasks: QualityTask[]; deleteTask: (id: string) => void }) {
  const navigate = useNavigate();
  return (
    <section className="panel">
      <h2>最近任务</h2>
      <div className="task-grid">
        {tasks.map((task) => (
          <article className="task-card" key={task.id}>
            <div><h3>{task.name}</h3><p>{task.businessType} · {task.testCases.length} 条用例</p></div>
            <div className="coverage-ring" style={{ ['--rate' as string]: `${task.coverage.overall}%` }}>{task.coverage.overall}%</div>
            <small>创建：{new Date(task.createdAt).toLocaleString()}</small>
            <small>更新：{new Date(task.updatedAt).toLocaleString()}</small>
            <div className="card-actions"><button onClick={() => navigate(`/task/${task.id}`)}>打开</button><button className="danger" onClick={() => window.confirm('确认删除该任务？') && deleteTask(task.id)}><Trash2 size={16} />删除</button></div>
          </article>
        ))}
      </div>
    </section>
  );
}

function NewTask({ addTask }: { addTask: (draft: TaskDraft) => QualityTask }) {
  const navigate = useNavigate();
  const [draft, setDraft] = useState<TaskDraft>({ name: '', businessType: '自动识别', requirement: '', riskTags: [] });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const submit = () => {
    const nextErrors: Record<string, string> = {};
    if (!draft.name.trim()) nextErrors.name = '请填写任务名称';
    if (!draft.requirement.trim()) nextErrors.requirement = '请填写需求正文';
    if (draft.requirement.trim().length > 0 && draft.requirement.trim().length < 20) nextErrors.requirement = '需求正文过短，请补充业务规则、状态或异常场景';
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    setBusy(true);
    const task = addTask(draft);
    navigate(`/task/${task.id}`);
  };
  const toggleRisk = (risk: string) => setDraft((value) => ({ ...value, riskTags: value.riskTags.includes(risk) ? value.riskTags.filter((item) => item !== risk) : [...value.riskTags, risk] }));
  return (
    <>
      <PageHeader title="新建测试任务" desc="输入任务名称、业务类型和需求正文，生成结构化测试资产。" />
      <section className="form-panel">
        <label>任务名称<input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />{errors.name && <span className="error">{errors.name}</span>}</label>
        <label>业务类型<select value={draft.businessType} onChange={(event) => setDraft({ ...draft, businessType: event.target.value })}>{businessTypes.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label>需求正文<textarea rows={8} value={draft.requirement} onChange={(event) => setDraft({ ...draft, requirement: event.target.value })} />{errors.requirement && <span className="error">{errors.requirement}</span>}</label>
        <div><span className="field-title">风险关注标签</span><div className="chips">{riskTagOptions.map((risk) => <button type="button" className={draft.riskTags.includes(risk) ? 'chip selected' : 'chip'} onClick={() => toggleRisk(risk)} key={risk}>{risk}</button>)}</div></div>
        <div className="actions"><button disabled={busy} onClick={submit}>分析并生成用例</button><button className="secondary" onClick={() => setDraft(examples[0])}>填入支付示例</button></div>
      </section>
    </>
  );
}

function HistoryPage({ tasks, deleteTask }: { tasks: QualityTask[]; deleteTask: (id: string) => void }) {
  return <><PageHeader title="历史任务" desc="从当前浏览器保存的任务记录中重新打开或删除任务。" />{tasks.length ? <TaskList tasks={tasks} deleteTask={deleteTask} /> : <EmptyState />}</>;
}

function ExamplesPage({ addTask }: { addTask: (draft: TaskDraft) => QualityTask }) {
  const navigate = useNavigate();
  return (
    <>
      <PageHeader title="示例需求" desc="选择一个内置业务需求，快速体验完整演示流程。" />
      <section className="task-grid">{examples.map((example) => <article className="task-card" key={example.name}><h3>{example.name}</h3><p>{example.requirement}</p><div className="chips">{example.riskTags.map((risk) => <span className="tag" key={risk}>{risk}</span>)}</div><button onClick={() => { const task = addTask(example); navigate(`/task/${task.id}`); }}>一键生成任务</button></article>)}</section>
    </>
  );
}

function AboutPage() {
  return (
    <>
      <PageHeader title="产品说明" desc="当前 Atoms-Demo 是现有 quality-agent 项目的可视化演示层。" />
      <section className="panel prose">
        <h2>它解决什么问题</h2><p>帮助测试人员、产品经理和开发人员，把自然语言业务需求拆解成规则、测试点、测试用例和覆盖缺口。</p>
        <h2>当前规则引擎如何工作</h2><p>系统基于关键词、句子内容和风险标签进行本地分析，不伪造大模型请求，不显示虚假的思考过程。</p>
        <h2>数据保存在哪里</h2><p>任务保存在当前浏览器 localStorage。清除浏览器数据可能导致记录丢失。</p>
        <h2>后续扩展</h2><p>可接入现有 FastAPI、V2 九节点工作流、V3 任务 API 和 SSE 事件流，用真实 Trace 与 Metrics 替换本地规则结果。</p>
      </section>
    </>
  );
}

function TaskDetail({ tasks, updateTask, deleteTask, autosave }: { tasks: QualityTask[]; updateTask: (task: QualityTask) => QualityTask; deleteTask: (id: string) => void; autosave: string }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const task = tasks.find((item) => item.id === id);
  const [tab, setTab] = useState('rules');
  const [query, setQuery] = useState('');
  const [priority, setPriority] = useState('全部');
  const [dimension, setDimension] = useState('全部');
  const [toast, setToast] = useState('');
  if (!task) return <><PageHeader title="任务不存在" desc="没有在当前浏览器中找到对应任务。" action={<button onClick={() => navigate('/')}>返回工作台</button>} /></>;

  const save = (next: QualityTask, text = '已保存') => { updateTask(next); setToast(text); window.setTimeout(() => setToast(''), 2200); };
  const addManual = () => {
    const point = task.testPoints[0];
    if (!point) return;
    const testCase = { ...buildCaseFromPoint(point, task.businessType, 'manual'), title: '手工新增测试用例' };
    save({ ...task, testCases: [...task.testCases, testCase] }, '已新增手工用例');
  };
  const filteredCases = useMemo(() => task.testCases.filter((item) => (query ? item.title.includes(query) || item.dimension.includes(query) : true) && (priority === '全部' || item.priority === priority) && (dimension === '全部' || item.dimension === dimension)), [task.testCases, query, priority, dimension]);
  const dimensions = ['全部', ...new Set(task.testCases.map((item) => item.dimension))];
  return (
    <>
      <PageHeader title={task.name} desc={`${task.businessType} · 综合覆盖率 ${task.coverage.overall}% · ${autosave}`} action={<div className="actions"><button className="secondary" onClick={() => navigate('/')}>返回工作台</button><button onClick={() => exportMarkdown(task)}>导出 Markdown</button><button onClick={() => exportJson(task)}>导出 JSON</button><button className="danger" onClick={() => { if (window.confirm('确认删除该任务？')) { deleteTask(task.id); navigate('/'); } }}>删除任务</button></div>} />
      {toast && <div className="toast">{toast}</div>}
      <section className="detail-summary"><Metric icon={<BarChart3 />} label="规则覆盖" value={`${task.coverage.ruleCoverage.rate}%`} /><Metric icon={<BarChart3 />} label="功能流程" value={`${task.coverage.functionalCoverage.rate}%`} /><Metric icon={<BarChart3 />} label="参数覆盖" value={`${task.coverage.parameterCoverage.rate}%`} /><Metric icon={<BarChart3 />} label="风险覆盖" value={`${task.coverage.riskCoverage.rate}%`} /></section>
      <div className="tabs">{[['rules', '需求规则'], ['points', '测试点'], ['cases', '测试用例'], ['coverage', '覆盖分析']].map(([key, label]) => <button className={tab === key ? 'active' : ''} onClick={() => setTab(key)} key={key}>{label}</button>)}</div>
      {tab === 'rules' && <section className="task-grid">{task.rules.map((rule) => <article className="task-card" key={rule.ruleId}><h3>{rule.ruleId}</h3><p>{rule.description}</p><div className="chips"><span className="tag">{rule.type}</span><span className={`tag ${rule.riskLevel}`}>{rule.riskLevel}</span>{rule.keywords.map((keyword) => <span className="tag" key={keyword}>{keyword}</span>)}</div><small>覆盖用例：{task.testCases.filter((item) => item.relatedRuleIds.includes(rule.ruleId)).length}</small></article>)}</section>}
      {tab === 'points' && <section className="task-grid">{task.testPoints.map((point) => <article className="task-card" key={point.pointId}><h3>{point.name}</h3><p>{point.category} · {point.dimension}</p><span className={point.covered ? 'status ok' : 'status warn'}>{point.covered ? '已覆盖' : '缺失覆盖'}</span><small>关联规则：{point.relatedRuleIds.join(', ')}</small></article>)}</section>}
      {tab === 'cases' && <CasePanel task={task} save={save} cases={filteredCases} query={query} setQuery={setQuery} priority={priority} setPriority={setPriority} dimension={dimension} setDimension={setDimension} dimensions={dimensions} addManual={addManual} />}
      {tab === 'coverage' && <CoveragePanel task={task} save={save} />}
    </>
  );
}

function CasePanel({ task, save, cases, query, setQuery, priority, setPriority, dimension, setDimension, dimensions, addManual }: { task: QualityTask; save: (task: QualityTask, text?: string) => void; cases: TestCase[]; query: string; setQuery: (v: string) => void; priority: string; setPriority: (v: string) => void; dimension: string; setDimension: (v: string) => void; dimensions: string[]; addManual: () => void }) {
  const updateCase = (patch: TestCase) => save({ ...task, testCases: task.testCases.map((item) => item.caseId === patch.caseId ? { ...patch, updatedAt: new Date().toISOString() } : item) });
  const removeCase = (id: string) => window.confirm('确认删除该用例？') && save({ ...task, testCases: task.testCases.filter((item) => item.caseId !== id) }, '已删除用例');
  const copyCase = (item: TestCase) => save({ ...task, testCases: [...task.testCases, { ...item, caseId: makeId('TC'), title: `${item.title} 副本`, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }] }, '已复制用例');
  return <section className="panel"><div className="filters"><input placeholder="搜索标题或维度" value={query} onChange={(event) => setQuery(event.target.value)} /><select value={priority} onChange={(event) => setPriority(event.target.value)}>{['全部', 'P0', 'P1', 'P2'].map((item) => <option key={item}>{item}</option>)}</select><select value={dimension} onChange={(event) => setDimension(event.target.value)}>{dimensions.map((item) => <option key={item}>{item}</option>)}</select><button className="secondary" onClick={() => { setQuery(''); setPriority('全部'); setDimension('全部'); }}>重置筛选</button><button onClick={addManual}>新增用例</button></div><div className="case-list">{cases.map((item) => <article className="case-card" key={item.caseId}><input value={item.title} onChange={(event) => updateCase({ ...item, title: event.target.value })} /><div className="case-meta"><select value={item.priority} onChange={(event) => updateCase({ ...item, priority: event.target.value as TestCase['priority'] })}><option>P0</option><option>P1</option><option>P2</option></select><select value={item.status} onChange={(event) => updateCase({ ...item, status: event.target.value as TestCase['status'] })}><option value="not_run">未执行</option><option value="passed">已通过</option><option value="failed">已失败</option></select><span>{item.dimension}</span><span>{item.generationSource}</span></div><TextList label="前置条件" values={item.preconditions} onChange={(values) => updateCase({ ...item, preconditions: values })} /><TextList label="测试步骤" values={item.steps} onChange={(values) => updateCase({ ...item, steps: values })} /><TextList label="预期结果" values={item.expectedResults} onChange={(values) => updateCase({ ...item, expectedResults: values })} /><div className="card-actions"><button className="secondary" onClick={() => copyCase(item)}>复制</button><button className="danger" onClick={() => removeCase(item.caseId)}>删除</button></div></article>)}</div></section>;
}

function TextList({ label, values, onChange }: { label: string; values: string[]; onChange: (values: string[]) => void }) {
  return <div className="text-list"><strong>{label}</strong>{values.map((value, index) => <div key={`${label}-${index}`}><input value={value} onChange={(event) => onChange(values.map((item, itemIndex) => itemIndex === index ? event.target.value : item))} /><button className="icon" aria-label={`删除${label}`} onClick={() => onChange(values.filter((_, itemIndex) => itemIndex !== index))}>×</button></div>)}<button className="secondary small" onClick={() => onChange([...values, ''])}>添加</button></div>;
}

function CoveragePanel({ task, save }: { task: QualityTask; save: (task: QualityTask, text?: string) => void }) {
  const fillGap = (dimension: string) => {
    const gap = task.coverage.missingDimensions.find((item) => item.dimension === dimension);
    if (!gap) return;
    const nextCases = supplementForGap(task.testPoints, task.testCases, task.businessType, gap);
    save({ ...task, testCases: nextCases }, `新增 ${nextCases.length - task.testCases.length} 条补充用例`);
  };
  const fillAll = () => {
    const nextCases = supplementAllGaps(task.testPoints, task.testCases, task.businessType, task.coverage.missingDimensions);
    save({ ...task, testCases: nextCases }, nextCases.length === task.testCases.length ? '当前没有可补充内容' : `新增 ${nextCases.length - task.testCases.length} 条补充用例`);
  };
  return <section className="panel"><div className="coverage-hero"><div className="coverage-ring large" style={{ ['--rate' as string]: `${task.coverage.overall}%` }}>{task.coverage.overall}%</div><div><h2>覆盖缺口分析</h2><p>已覆盖维度：{task.coverage.coveredDimensions.join('、') || '暂无'}</p><p>缺失维度：{task.coverage.missingDimensions.map((gap) => gap.dimension).join('、') || '无'}</p><button onClick={fillAll}>一键补齐全部缺口</button></div></div><div className="task-grid">{task.coverage.missingDimensions.length === 0 ? <article className="task-card"><h3>没有明显覆盖缺口</h3><p>当前规则、测试点和用例之间已经形成可追踪覆盖。</p></article> : task.coverage.missingDimensions.map((gap) => <article className="task-card" key={gap.dimension}><h3>{gap.dimension}</h3><p>{gap.risk}</p><p>{gap.recommendation}</p><button onClick={() => fillGap(gap.dimension)}>补充该维度用例</button></article>)}</div></section>;
}

export default App;
