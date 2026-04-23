export interface User {
  id: string;
  email: string;
  display_name: string;
  role: string;
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  language: string;
  framework?: string;
  created_at: string;
  updated_at: string;
  owner_id: string;
}

export interface ProjectCreate {
  name: string;
  description: string;
  language: string;
  framework?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  language?: string;
  framework?: string;
}

export interface ProjectMemory {
  terminology: TermEntry[];
  modules: ModuleEntry[];
  team: TeamMember[];
  history: HistoryEntry[];
}

export interface TermEntry {
  id: string;
  term: string;
  definition: string;
  context?: string;
  created_at: string;
}

export interface ModuleEntry {
  id: string;
  name: string;
  description: string;
  responsibilities: string[];
  dependencies: string[];
  created_at: string;
}

export interface TeamMember {
  id: string;
  name: string;
  role: string;
  expertise: string[];
  email?: string;
  created_at: string;
}

export interface HistoryEntry {
  id: string;
  event: string;
  details: string;
  timestamp: string;
}

export type AnalysisStatus =
  | 'pending'
  | 'queued'
  | 'extracting_requirements'
  | 'analyzing_risks'
  | 'generating_report'
  | 'completed'
  | 'failed';

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface AnalysisTask {
  id: string;
  project_id: string;
  status: AnalysisStatus;
  input_type: 'text' | 'file';
  input_preview: string;
  risk_level?: RiskLevel;
  risk_score?: number;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  error_message?: string;
}

export interface AnalysisCreate {
  project_id: string;
  text?: string;
}

export interface AnalysisProgress {
  step: number;
  total_steps: number;
  step_name: string;
  message: string;
  status: 'running' | 'completed' | 'failed';
}

export interface Report {
  task_id: string;
  title: string;
  summary: string;
  findings: Finding[];
  recommendations: Recommendation[];
  created_at: string;
}

export interface Finding {
  id: string;
  category: string;
  description: string;
  risk_level: RiskLevel;
  evidence: string;
}

export interface Recommendation {
  id: string;
  priority: number;
  description: string;
  rationale: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  display_name: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}
