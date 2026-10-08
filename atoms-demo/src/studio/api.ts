import type { GenerationEvent, ProjectListItem, StudioProject } from './types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

async function readError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string };
    return payload.detail ?? `请求失败（${response.status}）`;
  } catch {
    return `请求失败（${response.status}）`;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<T>;
}

export const studioApi = {
  listProjects: () => request<ProjectListItem[]>('/api/studio/projects'),

  getProject: (projectId: string, version?: number) => request<StudioProject>(
    `/api/studio/projects/${projectId}${version ? `?version=${version}` : ''}`,
  ),

  createProject: (title: string, requirement: string) => request<StudioProject>(
    '/api/studio/projects',
    { method: 'POST', body: JSON.stringify({ title, requirement }) },
  ),

  restoreVersion: async (projectId: string, version: number) => {
    const response = await request<{ project: StudioProject }>(
      `/api/studio/projects/${projectId}/versions/${version}/restore`,
      { method: 'POST' },
    );
    return response.project;
  },

  async generate(
    projectId: string,
    instruction: string,
    onEvent: (event: GenerationEvent) => void,
  ): Promise<void> {
    const response = await fetch(`${API_BASE}/api/studio/projects/${projectId}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction }),
    });
    if (!response.ok) throw new Error(await readError(response));
    if (!response.body) throw new Error('浏览器无法读取生成事件流');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() ?? '';
      for (const block of blocks) {
        const eventName = block.split('\n').find((line) => line.startsWith('event: '))?.slice(7);
        const dataLine = block.split('\n').find((line) => line.startsWith('data: '))?.slice(6);
        if (!eventName || !dataLine) continue;
        onEvent({
          type: eventName as GenerationEvent['type'],
          data: JSON.parse(dataLine) as GenerationEvent['data'],
        });
      }
      if (done) break;
    }
  },
};
