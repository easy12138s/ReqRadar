import { vi } from 'vitest'

export const mockFactory = {
  user: (overrides = {}) => ({
    id: 1,
    email: 'admin@reqradar.io',
    display_name: 'Admin',
    role: 'admin' as const,
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }),

  project: (overrides = {}) => ({
    id: '1',
    name: 'test-project',
    description: 'Test project for ReqRadar',
    source_type: 'local' as const,
    source_url: '',
    owner_id: 1,
    default_template_id: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
    ...overrides,
  }),

  analysisTask: (overrides = {}) => ({
    id: '1',
    requirement_text: '用户需要实现一个登录功能',
    project_id: '1',
    user_id: 1,
    status: 'completed' as const,
    depth: 'standard' as const,
    template_id: '1',
    error_message: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T01:00:00Z',
    ...overrides,
  }),

  report: (overrides = {}) => ({
    id: '1',
    task_id: '1',
    content: '# Test Report\n\nThis is a test report content.',
    risk_level: 'medium' as const,
    version: 1,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }),

  template: (overrides = {}) => ({
    id: '1',
    name: 'General Requirements Analysis',
    description: '通用需求分析模板',
    is_default: true,
    definition: JSON.stringify({
      sections: [
        { id: 'executive', title: '决策摘要', required: true },
        { id: 'technical', title: '技术分析', required: true },
      ],
    }),
    render_template: '# {{ title }}\n\n{{ content }}',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }),

  synonym: (overrides = {}) => ({
    id: '1',
    business_term: '用户登录',
    code_term: 'user_login',
    project_id: '1',
    priority: 'high' as const,
    source: 'manual' as const,
    created_at: '2024-01-01T00:00:00Z',
    ...overrides,
  }),

  version: (overrides = {}) => ({
    id: '1',
    report_id: '1',
    version: 2,
    content: '# Updated Report v2\n\nUpdated content here.',
    change_summary: 'Fixed typos and improved formatting',
    created_by: 1,
    created_at: '2024-01-01T12:00:00Z',
    ...overrides,
  }),

  evidence: (overrides = {}) => ({
    id: '1',
    type: 'code' as const,
    confidence: 'high' as const,
    source: 'src/auth/login.py:45',
    content: 'Found password validation logic',
    dimensions: ['understanding', 'evidence'],
    ...overrides,
  }),

  config: (overrides = {}) => ({
    key: 'llm.model',
    value: 'gpt-4o-mini',
    value_type: 'string' as const,
    is_sensitive: false,
    ...overrides,
  }),

  apiResponse: (data: any, status = 200) => ({
    data,
    status,
    headers: {},
  }),

  paginatedData: <T>(items: T[], page = 1, pageSize = 10) => ({
    items: items.slice((page - 1) * pageSize, page * pageSize),
    total: items.length,
    page,
    pageSize,
  }),
}

export const generateMockItems = <T>(count: number, factoryFn: (overrides?: any) => T): T[] =>
  Array.from({ length: count }, (_, i) => factoryFn({ id: String(i + 1) }))
