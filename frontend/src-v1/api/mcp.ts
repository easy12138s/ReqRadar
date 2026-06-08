import { apiClient } from './client';

export interface MCPConfigData {
  enabled: boolean;
  auto_start_with_web: boolean;
  host: string;
  port: number;
  path: string;
  public_url: string | null;
  audit_enabled: boolean;
  audit_retention_days: number;
}

export interface MCPAccessKey {
  id: number;
  user_id: number;
  key_prefix: string;
  name: string;
  scopes: string[];
  is_active: boolean;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string | null;
}

export interface MCPCreateKeyResult {
  mcp_config: {
    mcpServers: {
      reqradar: {
        url: string;
        auth: {
          type: string;
          token: string;
        };
      };
    };
  };
  key_prefix: string;
  name: string;
  note: string;
}

export interface MCPToolCall {
  id: number;
  access_key_id: number | null;
  tool_name: string;
  arguments_json: Record<string, unknown>;
  result_summary: string;
  duration_ms: number;
  success: boolean;
  error_message: string | null;
  created_at: string | null;
}

export interface MCPReExportResult {
  url: string;
  note: string;
}

export async function getMCPConfig(): Promise<MCPConfigData> {
  const response = await apiClient.get<MCPConfigData>('/mcp/config');
  return response.data;
}

export async function updateMCPConfig(data: Partial<MCPConfigData>): Promise<MCPConfigData> {
  const response = await apiClient.put<MCPConfigData>('/mcp/config', data);
  return response.data;
}

export async function listMCPKeys(): Promise<MCPAccessKey[]> {
  const response = await apiClient.get<MCPAccessKey[]>('/mcp/keys');
  return response.data;
}

export async function createMCPKey(name: string, scopes: string[] = ['read']): Promise<MCPCreateKeyResult> {
  const response = await apiClient.post<MCPCreateKeyResult>('/mcp/keys', { name, scopes });
  return response.data;
}

export async function revokeMCPKey(keyId: number): Promise<MCPAccessKey> {
  const response = await apiClient.post<MCPAccessKey>(`/mcp/keys/${keyId}/revoke`);
  return response.data;
}

export async function reExportMCPKey(keyId: number): Promise<MCPReExportResult> {
  const response = await apiClient.post<MCPReExportResult>(`/mcp/keys/${keyId}/re-export`);
  return response.data;
}

export async function listMCPToolCalls(params?: {
  access_key_id?: number;
  tool_name?: string;
  limit?: number;
  offset?: number;
}): Promise<MCPToolCall[]> {
  const response = await apiClient.get<MCPToolCall[]>('/mcp/tool-calls', { params });
  return response.data;
}

export async function cleanupMCPAudit(): Promise<{ deleted: number }> {
  const response = await apiClient.post<{ deleted: number }>('/mcp/audit/cleanup');
  return response.data;
}
