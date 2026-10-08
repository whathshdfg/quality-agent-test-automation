import {
  Bot,
  Check,
  ChevronDown,
  Code2,
  Download,
  LoaderCircle,
  MessageSquareText,
  Monitor,
  Plus,
  RefreshCw,
  RotateCcw,
  Send,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { studioApi } from './api';
import { buildPreviewDocument, installPreviewStorageBridge } from './preview';
import type { GenerationStage, ProjectListItem, StudioProject } from './types';

const EXAMPLE_REQUIREMENT = '生成一个订单管理应用，支持新增订单、按订单号搜索、按状态筛选、取消待支付订单，并在页面顶部展示订单数量和总金额。数据需要在刷新页面后保留。';

export function StudioPage() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [project, setProject] = useState<StudioProject | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [stage, setStage] = useState<GenerationStage | null>(null);
  const [error, setError] = useState('');
  const [newProjectOpen, setNewProjectOpen] = useState(false);
  const [title, setTitle] = useState('订单管理应用');
  const [requirement, setRequirement] = useState(EXAMPLE_REQUIREMENT);
  const [instruction, setInstruction] = useState('');
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);

  const refreshProjects = useCallback(async () => {
    const items = await studioApi.listProjects();
    setProjects(items);
    return items;
  }, []);

  useEffect(() => {
    refreshProjects()
      .then(async (items) => {
        if (items[0]) {
          const latest = await studioApi.getProject(items[0].id);
          setProject(latest);
          setSelectedVersion(latest.current_version);
        }
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : '无法连接生成服务'))
      .finally(() => setLoading(false));
  }, [refreshProjects]);

  const openProject = async (projectId: string) => {
    setError('');
    setLoading(true);
    try {
      const selected = await studioApi.getProject(projectId);
      setProject(selected);
      setSelectedVersion(selected.current_version);
      setStage(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '项目加载失败');
    } finally {
      setLoading(false);
    }
  };

  const runGeneration = async (projectId: string, nextInstruction: string) => {
    setGenerating(true);
    setError('');
    setStage({ stage: 'analysis', message: '正在建立生成任务' });
    try {
      await studioApi.generate(projectId, nextInstruction, (event) => {
        if (event.type === 'generation.stage') setStage(event.data);
        if (event.type === 'generation.failed') setError(event.data.message);
        if (event.type === 'generation.completed' && event.data.project) {
          setProject(event.data.project);
          setSelectedVersion(event.data.project.current_version);
          setInstruction('');
          setStage({ stage: 'validation', message: event.data.message });
        }
      });
      const latest = await studioApi.getProject(projectId);
      setProject(latest);
      setSelectedVersion(latest.current_version);
      await refreshProjects();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '生成请求失败');
    } finally {
      setGenerating(false);
    }
  };

  const createAndGenerate = async () => {
    if (!title.trim() || requirement.trim().length < 20) {
      setError('请填写项目名称，并输入至少 20 个字的应用需求');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const created = await studioApi.createProject(title.trim(), requirement.trim());
      setProject(created);
      setSelectedVersion(null);
      setNewProjectOpen(false);
      await refreshProjects();
      setLoading(false);
      await runGeneration(created.id, '');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '项目创建失败');
      setLoading(false);
    }
  };

  const viewVersion = async (version: number) => {
    if (!project) return;
    try {
      const selected = await studioApi.getProject(project.id, version);
      setProject(selected);
      setSelectedVersion(version);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '版本加载失败');
    }
  };

  const restoreVersion = async () => {
    if (!project || selectedVersion === null || selectedVersion === project.current_version) return;
    try {
      const restored = await studioApi.restoreVersion(project.id, selectedVersion);
      setProject(restored);
      setSelectedVersion(restored.current_version);
      await refreshProjects();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '版本恢复失败');
    }
  };

  const downloadSource = () => {
    if (!project?.version) return;
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([project.version.html], { type: 'text/html;charset=utf-8' }));
    link.download = `${project.title.replace(/[\\/:*?"<>|]/g, '-')}-v${project.version.version}.html`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  if (loading && !project) return <StudioLoading />;

  return (
    <div className="studio-page">
      <header className="studio-header">
        <div>
          <div className="eyebrow"><Bot size={15} /> 应用生成智能体</div>
          <h1>{project?.title ?? '从一句需求开始构建应用'}</h1>
          <p>{project ? `已保存 ${project.versions.length} 个版本 · ${statusText(project.status)}` : '生成、运行并持续修改一个真正可操作的单页应用。'}</p>
        </div>
        <div className="studio-header-actions">
          {projects.length > 0 && (
            <label className="project-picker">
              <span>项目</span>
              <select value={project?.id ?? ''} onChange={(event) => openProject(event.target.value)}>
                {projects.map((item) => <option value={item.id} key={item.id}>{item.title}</option>)}
              </select>
              <ChevronDown size={16} />
            </label>
          )}
          <button className="secondary" onClick={() => setNewProjectOpen(true)}><Plus size={17} />新建应用</button>
        </div>
      </header>

      {error && <div className="studio-alert"><strong>生成未完成</strong><span>{error}</span>{project && <button className="secondary small" disabled={generating} onClick={() => runGeneration(project.id, instruction)}><RefreshCw size={15} />重试</button>}</div>}

      {!project ? (
        <CreateProjectPanel title={title} requirement={requirement} setTitle={setTitle} setRequirement={setRequirement} submit={createAndGenerate} busy={loading || generating} />
      ) : (
        <div className="studio-workspace">
          <ConversationPane project={project} instruction={instruction} setInstruction={setInstruction} generating={generating} stage={stage} send={() => runGeneration(project.id, instruction)} />
          <CodePane project={project} selectedVersion={selectedVersion} viewVersion={viewVersion} restoreVersion={restoreVersion} downloadSource={downloadSource} />
          <PreviewPane project={project} />
        </div>
      )}

      {newProjectOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setNewProjectOpen(false)}>
          <div className="studio-modal" role="dialog" aria-modal="true" aria-label="新建应用" onMouseDown={(event) => event.stopPropagation()}>
            <div><div className="eyebrow"><Plus size={15} /> 新项目</div><h2>描述你想构建的应用</h2></div>
            <CreateProjectForm title={title} requirement={requirement} setTitle={setTitle} setRequirement={setRequirement} submit={createAndGenerate} busy={loading || generating} />
            <button className="secondary" onClick={() => setNewProjectOpen(false)}>取消</button>
          </div>
        </div>
      )}
    </div>
  );
}

function ConversationPane({ project, instruction, setInstruction, generating, stage, send }: { project: StudioProject; instruction: string; setInstruction: (value: string) => void; generating: boolean; stage: GenerationStage | null; send: () => void }) {
  return <section className="studio-pane conversation-pane">
    <PaneTitle icon={<MessageSquareText size={17} />} title="需求对话" hint="生成与修改记录" />
    <div className="conversation-list">
      {project.messages.map((message) => <article className={`message ${message.role}`} key={message.id}><span>{message.role === 'user' ? '你' : 'Agent'}</span><p>{message.content}</p></article>)}
      {generating && <article className="generation-progress"><LoaderCircle className="spin" size={18} /><div><strong>{stage?.message ?? '正在处理'}</strong><small>{stageLabel(stage?.stage)}</small>{stage?.errors?.map((item) => <em key={item}>{item}</em>)}</div></article>}
    </div>
    <div className="composer">
      <textarea rows={4} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="例如：增加金额统计，并支持按日期排序" disabled={generating} />
      <button onClick={send} disabled={generating || !instruction.trim()}><Send size={17} />发送修改</button>
    </div>
  </section>;
}

function CodePane({ project, selectedVersion, viewVersion, restoreVersion, downloadSource }: { project: StudioProject; selectedVersion: number | null; viewVersion: (version: number) => void; restoreVersion: () => void; downloadSource: () => void }) {
  const isCurrent = selectedVersion === project.current_version;
  return <section className="studio-pane code-pane">
    <PaneTitle icon={<Code2 size={17} />} title="生成文件" hint="index.html" />
    <div className="code-toolbar">
      <select value={selectedVersion ?? ''} onChange={(event) => viewVersion(Number(event.target.value))} disabled={!project.versions.length} aria-label="选择版本">
        {!project.versions.length && <option value="">暂无版本</option>}
        {project.versions.map((item) => <option value={item.version} key={item.version}>v{item.version} · {item.summary}</option>)}
      </select>
      <button className="icon secondary" aria-label="下载源码" title="下载源码" onClick={downloadSource} disabled={!project.version}><Download size={16} /></button>
      {!isCurrent && <button className="secondary small" onClick={restoreVersion}><RotateCcw size={15} />恢复此版本</button>}
    </div>
    {project.version ? <CodeViewer code={project.version.html} /> : <PaneEmpty icon={<Code2 />} title="等待首次生成" text="模型返回并通过校验后，完整源码会显示在这里。" />}
  </section>;
}

function CodeViewer({ code }: { code: string }) {
  const lines = useMemo(() => code.split('\n'), [code]);
  return <div className="code-viewer" role="region" aria-label="生成源码"><ol>{lines.map((line, index) => <li key={index}><code>{line || ' '}</code></li>)}</ol></div>;
}

function PreviewPane({ project }: { project: StudioProject }) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const document = project.version ? buildPreviewDocument(project.version.html, project.id) : '';

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !project.version) return;
    return installPreviewStorageBridge(iframe, project.id);
  }, [project.id, project.version, refreshKey]);

  return <section className="studio-pane preview-pane">
    <PaneTitle icon={<Monitor size={17} />} title="运行预览" hint={project.version ? `v${project.version.version}` : '等待生成'} action={<div className="pane-icons"><button className="icon secondary" title="刷新预览" aria-label="刷新预览" onClick={() => setRefreshKey((value) => value + 1)} disabled={!project.version}><RefreshCw size={16} /></button></div>} />
    {project.version ? <div className="preview-frame"><div className="browser-bar"><i /><i /><i /><span>隔离预览 · 网络访问已禁用</span></div><iframe key={`${project.version.version}-${refreshKey}`} ref={iframeRef} title={`${project.title} 预览`} sandbox="allow-scripts" srcDoc={document} /></div> : <PaneEmpty icon={<Monitor />} title="应用将在这里运行" text="首次生成完成后，可以直接操作页面并验证交互。" />}
  </section>;
}

function PaneTitle({ icon, title, hint, action }: { icon: React.ReactNode; title: string; hint: string; action?: React.ReactNode }) {
  return <header className="pane-title"><div>{icon}<strong>{title}</strong><small>{hint}</small></div>{action}</header>;
}

function PaneEmpty({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return <div className="pane-empty"><span>{icon}</span><strong>{title}</strong><p>{text}</p></div>;
}

function CreateProjectPanel(props: CreateFormProps) {
  return <section className="create-project-panel"><div className="create-copy"><span><Bot size={22} /></span><h2>生成你的第一个应用</h2><p>描述真实业务目标和核心操作，Agent 将生成完整代码并在隔离环境中运行。</p><div className="flow-points"><span><Check size={15} />真实模型生成</span><span><Check size={15} />版本自动保存</span><span><Check size={15} />可交互网页预览</span></div></div><CreateProjectForm {...props} /></section>;
}

interface CreateFormProps { title: string; requirement: string; setTitle: (value: string) => void; setRequirement: (value: string) => void; submit: () => void; busy: boolean }
function CreateProjectForm({ title, requirement, setTitle, setRequirement, submit, busy }: CreateFormProps) {
  return <div className="create-form"><label>应用名称<input value={title} maxLength={80} onChange={(event) => setTitle(event.target.value)} /></label><label>应用需求<textarea rows={7} value={requirement} maxLength={12000} onChange={(event) => setRequirement(event.target.value)} /></label><div className="form-foot"><small>{requirement.trim().length} / 12000</small><button onClick={submit} disabled={busy}>{busy ? <LoaderCircle className="spin" size={17} /> : <Bot size={17} />}创建并生成</button></div></div>;
}

function StudioLoading() {
  return <div className="studio-loading"><LoaderCircle className="spin" /><span>正在连接应用生成服务</span></div>;
}

function statusText(status: StudioProject['status']): string {
  return { draft: '等待生成', generating: '正在生成', ready: '可以运行', failed: '上次生成失败' }[status];
}

function stageLabel(stage?: GenerationStage['stage']): string {
  return { analysis: '需求分析', generation: '代码生成', validation: '结构与安全校验', repair: '自动修复' }[stage ?? 'analysis'];
}
