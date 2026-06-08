import { apiClient } from './client';
import type { ChatRequest, ChatResponse, ChatMessage } from '@/types/api';

export async function sendChatMessage(taskId: string, data: ChatRequest): Promise<ChatResponse> {
  const response = await apiClient.post<ChatResponse>(`/analyses/${taskId}/chat`, data);
  return response.data;
}

export async function getChatHistory(taskId: string, versionNumber?: number): Promise<{ messages: ChatMessage[] }> {
  const params = versionNumber !== undefined ? { version_number: versionNumber } : {};
  const response = await apiClient.get<{ messages: ChatMessage[] }>(`/analyses/${taskId}/chat`, { params });
  return response.data;
}

export async function saveChatVersion(taskId: string, versionNumber: number): Promise<{ success: boolean; new_version?: number }> {
  const response = await apiClient.post(`/analyses/${taskId}/chat/save`, { version_number: versionNumber });
  return response.data;
}
