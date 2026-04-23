import { apiClient } from './client';
import type {
  HistoryEntry,
  ModuleEntry,
  Project,
  ProjectCreate,
  ProjectMemory,
  ProjectUpdate,
  TeamMember,
  TermEntry,
} from '@/types/api';

export async function getProjects(): Promise<Project[]> {
  const response = await apiClient.get<Project[]>('/projects');
  return response.data;
}

export async function createProject(data: ProjectCreate): Promise<Project> {
  const response = await apiClient.post<Project>('/projects', data);
  return response.data;
}

export async function getProject(id: string): Promise<Project> {
  const response = await apiClient.get<Project>(`/projects/${id}`);
  return response.data;
}

export async function updateProject(
  id: string,
  data: ProjectUpdate
): Promise<Project> {
  const response = await apiClient.put<Project>(`/projects/${id}`, data);
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
