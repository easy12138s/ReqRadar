import { apiClient } from './client';

export interface UserInfo {
  id: number;
  email: string;
  display_name: string;
  role: string;
  created_at: string;
}

export async function getUsers(): Promise<UserInfo[]> {
  const { data } = await apiClient.get('/users');
  return data;
}

export async function updateUser(userId: number, body: { role?: string; display_name?: string }): Promise<void> {
  await apiClient.put(`/users/${userId}`, body);
}

export async function deleteUser(userId: number): Promise<void> {
  await apiClient.delete(`/users/${userId}`);
}
