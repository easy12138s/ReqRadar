import axios from 'axios';
import type { LoginRequest, LoginResponse, VerifyTokenResponse } from '@/types';

const client = axios.create({
  baseURL: '/api/v2',
});

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const response = await client.post<LoginResponse>('/auth/login', data);
  return response.data;
}

export async function verifyToken(token: string): Promise<VerifyTokenResponse> {
  const response = await client.get<VerifyTokenResponse>('/auth/verify', {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response.data;
}
