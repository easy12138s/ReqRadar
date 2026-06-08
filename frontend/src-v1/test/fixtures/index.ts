export const fixtures = {
  users: {
    admin: { email: 'admin@reqradar.io', password: 'Admin12138%', role: 'admin' },
    regular: { email: 'user@test.com', password: 'User12345%', role: 'user' },
  },

  projects: {
    pythonBackend: { name: 'python-api', language: 'Python', modules: 12 },
    reactFrontend: { name: 'react-dashboard', language: 'TypeScript', modules: 8 },
    fullStack: { name: 'fullstack-app', language: 'Mixed', modules: 20 },
  },

  requirements: {
    simpleLogin: { title: 'Login Feature', complexity: 'low' },
    complexPayment: { title: 'Payment System', complexity: 'high' },
    ambiguousReporting: { title: 'Reports Module', clarity: 'low' },
  },

  analyses: {
    completedSuccess: { status: 'completed', riskLevel: 'medium' },
    failedTimeout: { status: 'failed', error: 'LLM timeout' },
    cancelledByUser: { status: 'cancelled' },
  },

  riskLevels: ['low', 'medium', 'high', 'critical'] as const,

  depthLevels: ['quick', 'standard', 'deep'] as const,

  focusAreas: [
    { key: 'security', label: '安全性' },
    { key: 'performance', label: '性能' },
    { key: 'ux', label: '用户体验' },
    { key: 'scalability', label: '可扩展性' },
    { key: 'maintainability', label: '可维护性' },
  ],
}
