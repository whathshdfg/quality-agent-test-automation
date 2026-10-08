export type ProjectStatus = 'draft' | 'generating' | 'ready' | 'failed';

export interface StudioMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export interface VersionSummary {
  version: number;
  summary: string;
  created_at: string;
}

export interface AppVersion extends VersionSummary {
  html: string;
}

export interface StudioProject {
  id: string;
  title: string;
  requirement: string;
  status: ProjectStatus;
  error: string | null;
  current_version: number | null;
  version: AppVersion | null;
  versions: VersionSummary[];
  messages: StudioMessage[];
  created_at: string;
  updated_at: string;
}

export interface ProjectListItem {
  id: string;
  title: string;
  status: ProjectStatus;
  current_version: number | null;
  created_at: string;
  updated_at: string;
}

export interface GenerationStage {
  stage: 'analysis' | 'generation' | 'validation' | 'repair';
  message: string;
  errors?: string[];
}

export interface GenerationEvent {
  type: 'generation.stage' | 'generation.completed' | 'generation.failed';
  data: GenerationStage & { project?: StudioProject };
}
