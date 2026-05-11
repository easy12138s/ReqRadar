export const mockUser = {
  id: 1,
  email: 'admin@reqradar.io',
  display_name: 'Admin',
  role: 'admin',
  created_at: '2024-01-01T00:00:00Z',
}

export const mockProject = {
  id: 1,
  name: 'test-project',
  description: 'Test project for ReqRadar',
  source_type: 'local' as const,
  source_url: '',
  owner_id: 1,
  default_template_id: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
}

export const mockAnalysisTask = {
  id: 1,
  requirement_text: '用户需要实现一个登录功能',
  project_id: 1,
  user_id: 1,
  status: 'completed' as const,
  depth: 'standard' as const,
  template_id: 1,
  error_message: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T01:00:00Z',
}

export const mockReport = {
  id: 1,
  task_id: 1,
  content: '# Test Report\n\nThis is a test report content.',
  risk_level: 'medium' as const,
  version: 1,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

export const mockRequirementDocument = {
  id: 1,
  project_id: 1,
  user_id: 1,
  title: 'Login Feature Requirements',
  consolidated_text: '# Login Feature\n\n## Functional Requirements\n\nFR-01: User should be able to login with email and password.',
  source_files: [
    { filename: 'requirements.pdf', type: '.pdf', size: 102400, stored_path: '/tmp/req_001.pdf' },
  ],
  status: 'ready' as const,
  version: 1,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
}

export const mockTemplate = {
  id: 1,
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
}

export const mockSynonym = {
  id: 1,
  business_term: '用户登录',
  code_term: 'user_login',
  project_id: 1,
  priority: 'high' as const,
  source: 'manual' as const,
  created_at: '2024-01-01T00:00:00Z',
}

export const mockVersion = {
  id: 1,
  report_id: 1,
  version: 2,
  content: '# Updated Report v2\n\nUpdated content here.',
  change_summary: 'Fixed typos and improved formatting',
  created_by: 1,
  created_at: '2024-01-01T12:00:00Z',
}

export const mockConfig = {
  key: 'llm.model',
  value: 'gpt-4o-mini',
  value_type: 'string',
  is_sensitive: false,
}

export const mockProjectsList = [mockProject, { ...mockProject, id: 2, name: 'project-2' }]

export const mockAnalysisTasksList = [mockAnalysisTask, { ...mockAnalysisTask, id: 2, status: 'running' }]

export const mockTemplatesList = [mockTemplate, { ...mockTemplate, id: 2, name: 'Security Audit', is_default: false }]

export const mockAuthResponse = {
  access_token: 'test-jwt-token-12345',
  token_type: 'bearer',
  expires_in: 86400,
}
