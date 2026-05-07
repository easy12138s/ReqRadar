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
  source_type: 'zip' | 'git' | 'local';
  source_url: string;
  created_at: string;
  updated_at: string;
  owner_id: string;
}

export interface ProjectCreateFromLocal {
  name: string;
  description: string;
  local_path: string;
}

export interface ProjectCreateFromGit {
  name: string;
  description: string;
  git_url: string;
  branch?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
}

export interface FileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  children?: FileTreeNode[];
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
  id: number;
  project_id: number;
  project_name: string;
  requirement_name: string;
  requirement_text: string;
  status: AnalysisStatus;
  risk_level?: RiskLevel;
  risk_score?: number;
  error_message?: string;
  depth?: AnalysisDepth;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface AnalysisCreate {
  project_id: number;
  text?: string;
  depth?: AnalysisDepth;
  template_id?: string;
  focus_areas?: string[];
  requirement_document_id?: number;
}

export interface AnalysisProgress {
  step: number;
  total_steps: number;
  step_name: string;
  message: string;
  status: 'running' | 'completed' | 'failed';
}

export interface Report {
  task_id: number;
  content_markdown: string;
  content_html: string;
  risk_level: string;
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

// === Round 3 新增类型 ===

export type AnalysisDepth = 'quick' | 'standard' | 'deep';

export interface SynonymMapping {
  id: string;
  project_id: string | null;
  business_term: string;
  code_terms: string[];
  priority: number;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface SynonymMappingCreate {
  project_id?: string;
  business_term: string;
  code_terms: string[];
  priority?: number;
}

export interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  definition_yaml: string;
  created_at: string;
  updated_at: string;
}

export interface ReportTemplateCreate {
  name: string;
  description: string;
  definition_yaml: string;
}

export interface ReportVersion {
  version_number: number;
  trigger_type: string;
  trigger_description: string;
  created_at: string;
  created_by: string;
}

export interface ReportVersionDetail extends ReportVersion {
  content_markdown: string;
  content_html: string;
  report_data: Record<string, unknown>;
}

export interface ChatMessage {
  id: number | string;
  role: 'user' | 'assistant' | 'agent';
  content: string;
  version_number?: number;
  intent_type?: string;
  created_at: string;
}

export interface ChatRequest {
  message: string;
  version_number?: number;
}

export interface ChatResponse {
  reply: string;
  intent_type: string;
  updated: boolean;
  new_version?: number;
  report_preview?: string;
}

export interface EvidenceItem {
  id: string;
  type: string;
  source: string;
  content: string;
  confidence: string;
  dimensions: string[];
  timestamp: string;
}

export interface PendingChange {
  id: string;
  type: 'profile' | 'synonym';
  description: string;
  old_value?: string;
  new_value?: string;
  status: 'pending' | 'accepted' | 'rejected';
  created_at: string;
}

export interface UserPreference {
  default_depth: AnalysisDepth;
  report_language: string;
  focus_areas: string[];
}

export interface ProjectProfileData {
  name: string;
  overview: string;
  tech_stack: Record<string, string[]>;
  modules: Array<{
    name: string;
    responsibility: string;
    key_classes: string[];
    dependencies: string[];
  }>;
  terms: Array<{ term: string; definition: string; domain: string }>;
  constraints: Array<{ description: string; type: string }>;
  changelog: Array<{ date: string; description: string }>;
}

export interface ProjectProfile {
  content: string;
  data: ProjectProfileData;
}
