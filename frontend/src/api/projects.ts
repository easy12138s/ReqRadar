import { apiClient } from './client';
import type {
  FileTreeNode,
  HistoryEntry,
  ModuleEntry,
  Project,
  ProjectCreateFromGit,
  ProjectCreateFromLocal,
  ProjectMemory,
  ProjectUpdate,
  TeamMember,
  TermEntry,
} from '@/types/api';

export async function getProjects(): Promise<Project[]> {
  const response = await apiClient.get<Project[]>('/projects');
  return response.data;
}

export interface ProjectDashboardSummary {
  id: number;
  name: string;
  terms_count: number;
  modules_count: number;
  pending_changes_count: number;
  updated_at: string;
}

export async function getDashboardSummaries(): Promise<ProjectDashboardSummary[]> {
  const response = await apiClient.get<ProjectDashboardSummary[]>('/projects/dashboard-summaries');
  return response.data;
}

export async function createFromLocal(data: ProjectCreateFromLocal): Promise<Project> {
  const response = await apiClient.post<Project>('/projects/from-local', data);
  return response.data;
}

export async function createFromGit(data: ProjectCreateFromGit): Promise<Project> {
  const response = await apiClient.post<Project>('/projects/from-git', data);
  return response.data;
}

export async function createFromZip(
  name: string,
  description: string,
  file: File,
): Promise<Project> {
  const formData = new FormData();
  formData.append('name', name);
  formData.append('description', description);
  formData.append('file', file);
  const response = await apiClient.post<Project>('/projects/from-zip', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function getProject(id: string): Promise<Project> {
  const response = await apiClient.get<Project>(`/projects/${id}`);
  return response.data;
}

export async function updateProject(
  id: string,
  data: ProjectUpdate,
): Promise<Project> {
  const response = await apiClient.put<Project>(`/projects/${id}`, data);
  return response.data;
}

export async function deleteProject(id: string): Promise<void> {
  await apiClient.delete(`/projects/${id}`);
}

export async function getProjectFiles(id: string): Promise<FileTreeNode[]> {
  const response = await apiClient.get<FileTreeNode[]>(`/projects/${id}/files`);
  return response.data;
}

export async function getProjectMemory(id: string): Promise<ProjectMemory> {
  const [terminologyRes, modulesRes, teamRes, historyRes] = await Promise.all([
    apiClient.get<TermEntry[]>(`/projects/${id}/terminology`),
    apiClient.get<ModuleEntry[]>(`/projects/${id}/modules`),
    apiClient.get<TeamMember[]>(`/projects/${id}/team`),
    apiClient.get<HistoryEntry[]>(`/projects/${id}/history`),
  ]);

  return {
    terminology: terminologyRes.data,
    modules: modulesRes.data,
    team: teamRes.data,
    history: historyRes.data,
  };
}
