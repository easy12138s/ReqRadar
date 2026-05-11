import { vi } from 'vitest'

export const createApiMock = () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  patch: vi.fn(),
})

export const mockApiClient = {
  get: vi.fn().mockResolvedValue({ data: [] }),
  post: vi.fn().mockResolvedValue({ data: {} }),
  put: vi.fn().mockResolvedValue({ data: {} }),
  delete: vi.fn().mockResolvedValue({ data: null }),
  patch: vi.fn().mockResolvedValue({ data: {} }),
}

export const mockWebSocket = {
  onopen: vi.fn(),
  onclose: vi.fn(),
  onerror: vi.fn(),
  onmessage: vi.fn(),
  send: vi.fn(),
  close: vi.fn(),
  readyState: WebSocket.OPEN,
}

vi.mock('@/api/client', () => ({
  apiClient: mockApiClient,
  setNavigate: vi.fn(),
}))
