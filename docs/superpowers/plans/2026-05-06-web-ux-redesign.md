# Web 模块 Phase 1 重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 补齐功能缺口、重构页面布局、建立深色科技风品牌视觉体系 — 新建 AppShell Layout、Dashboard 首页、ErrorBoundary、WebSocket 重连、Skeleton 加载

**Architecture:** 水平 TopBar + 单层 Main 替代旧双层 Layout 嵌套。深色科技风主题（青 `#00d4ff` + 紫 `#7c3aed`）。新增 ErrorBoundary 包裹 Outlet，useWebSocket hook 提供指数退避重连。

**Tech Stack:** React 19, TypeScript 6, Ant Design 6, react-router-dom 7, Vite 8

**Spec:** `docs/superpowers/specs/2026-05-06-web-ux-redesign-design.md`

---

## 文件地图

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/i18n/index.ts` | 新建 | i18n 初始化 + useTranslation |
| `src/i18n/locales/zh-CN.ts` | 新建 | 中文翻译 |
| `src/i18n/locales/en-US.ts` | 新建 | 英文骨架 |
| `src/components/ErrorBoundary.tsx` | 新建 | 全局异常捕获 |
| `src/components/SkeletonCard.tsx` | 新建 | 卡片骨架屏 |
| `src/components/SkeletonTable.tsx` | 新建 | 表格骨架屏 |
| `src/components/SkeletonStat.tsx` | 新建 | 统计卡片骨架屏 |
| `src/hooks/useWebSocket.ts` | 新建 | WebSocket 自动重连 hook |
| `src/components/AppShell.tsx` | 新建 | 新 Layout（TopBar+Main） |
| `src/pages/Dashboard.tsx` | 新建 | 知识向首页 |
| `src/App.tsx` | 修改 | 接入 AppShell + ErrorBoundary + 主题 |
| `src/main.tsx` | 修改 | 引入 i18n |
| `src/index.css` | 修改 | 深色背景 + 毛玻璃工具类 |
| `src/contexts/AuthContext.tsx` | 修改 | logout 改 SPA 导航 |
| `src/pages/Login.tsx` | 修改 | 分离 loading 状态 + 显示后端错误 |
| `src/pages/Projects.tsx` | 修改 | 新增删除 + 搜索 |
| `src/pages/ProjectDetail.tsx` | 修改 | 新增删除 + 提交分析 CTA |
| `src/pages/ProjectProfile.tsx` | 修改 | 补齐字段 |
| `src/pages/AnalysisSubmit.tsx` | 修改 | Tab 状态保持 |
| `src/pages/AnalysisProgress.tsx` | 修改 | useWebSocket |
| `src/pages/ReportView.tsx` | 修改 | TOC scrollIntoView |
| `src/pages/LLMConfig.tsx` | 修改 | 测试连接按钮 |
| `src/AppLayout.tsx` | 删除 | 被 AppShell 替换 |
| `src/components/NavMenu.tsx` | 删除 | 导航移入 TopBar |
| `src/pages/SettingsLayout.tsx` | 删除 | 消除嵌套 |
| `src/App.css` | 删除 | 183 行死代码 |

---

### Task 1: Foundation — i18n + Skeleton Components + ErrorBoundary

**Files:**
- Create: `frontend/src/i18n/index.ts`
- Create: `frontend/src/i18n/locales/zh-CN.ts`
- Create: `frontend/src/i18n/locales/en-US.ts`
- Create: `frontend/src/components/ErrorBoundary.tsx`
- Create: `frontend/src/components/SkeletonCard.tsx`
- Create: `frontend/src/components/SkeletonTable.tsx`
- Create: `frontend/src/components/SkeletonStat.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Create i18n index and locales**

Create `frontend/src/i18n/locales/zh-CN.ts`:
```typescript
const zhCN = {
  common: {
    loading: '加载中...',
    save: '保存',
    cancel: '取消',
    delete: '删除',
    confirm: '确认',
    search: '搜索',
    back: '返回',
    refresh: '刷新',
  },
  nav: {
    dashboard: 'Dashboard',
    projects: '项目',
    analyses: '分析',
    settings: '设置',
  },
  auth: {
    login: '登录',
    register: '注册',
    logout: '退出登录',
    email: '邮箱',
    password: '密码',
    displayName: '显示名称',
    confirmPassword: '确认密码',
    loginFailed: '登录失败',
    registerFailed: '注册失败',
  },
  dashboard: {
    welcome: '欢迎回来',
    totalProjects: '项目',
    totalTerms: '术语',
    totalModules: '模块',
    pendingChanges: '待确认变更',
    recentMemoryUpdates: '最近记忆更新',
    quickActions: '快捷操作',
    newProject: '新建项目',
    submitAnalysis: '提交分析',
    manageTemplates: '管理模板',
    configLLM: '配置 LLM',
    noProjects: '还没有项目',
    createFirst: '创建第一个项目开始使用',
  },
  project: {
    create: '新建项目',
    delete: '删除项目',
    deleteConfirm: '确定要删除这个项目吗？此操作不可撤销。',
    name: '项目名称',
    description: '项目描述',
    sourceType: '来源类型',
    localPath: '本地路径',
    gitUrl: 'Git URL',
    zipUpload: 'ZIP 上传',
    overview: '概览',
    fileBrowser: '文件浏览',
    knowledge: '知识库',
    profile: '项目画像',
    submitAnalysis: '提交需求分析',
  },
  analysis: {
    submit: '提交分析',
    textInput: '文本输入',
    fileUpload: '文件上传',
    requirementText: '需求描述',
    depth: '分析深度',
    quick: '快速',
    standard: '标准',
    deep: '深度',
    status: {
      pending: '等待中',
      running: '运行中',
      completed: '已完成',
      failed: '失败',
      cancelled: '已取消',
    },
    stop: '停止并生成报告',
    retry: '重试',
    viewReport: '查看报告',
    progress: '分析进度',
  },
  report: {
    title: '分析报告',
    summary: '摘要',
    findings: '发现',
    recommendations: '建议',
    downloadMd: '下载 MD',
    noReport: '暂无报告',
    versions: '版本历史',
    evidence: '证据链',
  },
  errors: {
    somethingWrong: '页面出现异常',
    clickToRefresh: '点击刷新页面',
    networkError: '网络错误，请检查连接',
  },
  ws: {
    connecting: '连接中...',
    connected: '已连接',
    disconnected: '连接断开',
    reconnecting: '重连中...',
  },
};

export default zhCN;
export type Locale = typeof zhCN;
```

Create `frontend/src/i18n/locales/en-US.ts`:
```typescript
import type { Locale } from './zh-CN';

const enUS: Locale = {
  common: {
    loading: 'Loading...',
    save: 'Save',
    cancel: 'Cancel',
    delete: 'Delete',
    confirm: 'Confirm',
    search: 'Search',
    back: 'Back',
    refresh: 'Refresh',
  },
  nav: {
    dashboard: 'Dashboard',
    projects: 'Projects',
    analyses: 'Analyses',
    settings: 'Settings',
  },
  auth: {
    login: 'Log In',
    register: 'Register',
    logout: 'Log Out',
    email: 'Email',
    password: 'Password',
    displayName: 'Display Name',
    confirmPassword: 'Confirm Password',
    loginFailed: 'Login failed',
    registerFailed: 'Register failed',
  },
  dashboard: {
    welcome: 'Welcome back',
    totalProjects: 'Projects',
    totalTerms: 'Terms',
    totalModules: 'Modules',
    pendingChanges: 'Pending',
    recentMemoryUpdates: 'Recent Memory Updates',
    quickActions: 'Quick Actions',
    newProject: 'New Project',
    submitAnalysis: 'Submit Analysis',
    manageTemplates: 'Manage Templates',
    configLLM: 'Configure LLM',
    noProjects: 'No projects yet',
    createFirst: 'Create your first project to get started',
  },
  project: {
    create: 'New Project',
    delete: 'Delete Project',
    deleteConfirm: 'Delete this project? This cannot be undone.',
    name: 'Project Name',
    description: 'Description',
    sourceType: 'Source Type',
    localPath: 'Local Path',
    gitUrl: 'Git URL',
    zipUpload: 'ZIP Upload',
    overview: 'Overview',
    fileBrowser: 'Files',
    knowledge: 'Knowledge',
    profile: 'Profile',
    submitAnalysis: 'Submit Analysis',
  },
  analysis: {
    submit: 'Submit Analysis',
    textInput: 'Text Input',
    fileUpload: 'File Upload',
    requirementText: 'Requirement Description',
    depth: 'Depth',
    quick: 'Quick',
    standard: 'Standard',
    deep: 'Deep',
    status: {
      pending: 'Pending',
      running: 'Running',
      completed: 'Completed',
      failed: 'Failed',
      cancelled: 'Cancelled',
    },
    stop: 'Stop & Report',
    retry: 'Retry',
    viewReport: 'View Report',
    progress: 'Progress',
  },
  report: {
    title: 'Analysis Report',
    summary: 'Summary',
    findings: 'Findings',
    recommendations: 'Recommendations',
    downloadMd: 'Download MD',
    noReport: 'No report',
    versions: 'Versions',
    evidence: 'Evidence',
  },
  errors: {
    somethingWrong: 'Something went wrong',
    clickToRefresh: 'Click to refresh the page',
    networkError: 'Network error, please check your connection',
  },
  ws: {
    connecting: 'Connecting...',
    connected: 'Connected',
    disconnected: 'Disconnected',
    reconnecting: 'Reconnecting...',
  },
};

export default enUS;
```

Create `frontend/src/i18n/index.ts`:
```typescript
import { useCallback } from 'react';
import zhCN from './locales/zh-CN';

const _locales: Record<string, typeof zhCN> = {};
let _currentLocale = 'zh-CN';

async function loadLocale(locale: string) {
  if (locale === 'zh-CN') {
    _locales[locale] = zhCN;
  } else {
    const mod = await import(`./locales/${locale}.ts`);
    _locales[locale] = mod.default;
  }
}

export function t(path: string): string {
  const keys = path.split('.');
  let value: unknown = _locales[_currentLocale] || zhCN;
  for (const key of keys) {
    if (value && typeof value === 'object') {
      value = (value as Record<string, unknown>)[key];
    } else {
      return path;
    }
  }
  return typeof value === 'string' ? value : path;
}

export function useTranslation() {
  const translate = useCallback((path: string) => t(path), []);
  return { t: translate };
}

export default loadLocale;
```

- [ ] **Step 2: Create ErrorBoundary**

Create `frontend/src/components/ErrorBoundary.tsx`:
```tsx
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button, Result } from 'antd';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <Result
          status="error"
          title="页面出现异常"
          subTitle={import.meta.env.DEV ? this.state.error?.message : undefined}
          extra={
            <Button type="primary" onClick={() => window.location.reload()}>
              刷新页面
            </Button>
          }
        />
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 3: Create Skeleton components**

Create `frontend/src/components/SkeletonCard.tsx`:
```tsx
import { Skeleton } from 'antd';

export default function SkeletonCard({ count = 3 }: { count?: number }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={{ padding: 16, background: 'var(--card-bg, #0f1624)', borderRadius: 12, border: '1px solid #1e293b' }}>
          <Skeleton active paragraph={{ rows: 3 }} />
        </div>
      ))}
    </div>
  );
}
```

Create `frontend/src/components/SkeletonTable.tsx`:
```tsx
import { Skeleton } from 'antd';

export default function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div style={{ padding: 16, background: 'var(--card-bg, #0f1624)', borderRadius: 12, border: '1px solid #1e293b' }}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} active paragraph={{ rows: 1 }} title={false} style={{ marginBottom: 8 }} />
      ))}
    </div>
  );
}
```

Create `frontend/src/components/SkeletonStat.tsx`:
```tsx
import { Skeleton } from 'antd';

export default function SkeletonStat({ count = 4 }: { count?: number }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={{ padding: 20, background: 'var(--card-bg, #0f1624)', borderRadius: 12, border: '1px solid #1e293b' }}>
          <Skeleton active paragraph={{ rows: 1 }} title={{ width: '40%' }} />
          <Skeleton.Input active size="large" style={{ marginTop: 8, width: '60%' }} />
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Update main.tsx and index.css**

In `frontend/src/main.tsx`, add i18n import at top:
```typescript
import './i18n';
```

Replace `frontend/src/index.css` entirely:
```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
  background: #0a0e17;
  color: #c9d1d9;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.glass {
  background: rgba(15, 22, 36, 0.8);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.glass-card {
  background: rgba(15, 22, 36, 0.7);
  border: 1px solid #1e293b;
  border-radius: 12px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.markdown-body {
  max-width: 820px;
  margin: 0 auto;
  padding: 24px 0;
  font-size: 15px;
  line-height: 1.8;
  color: #c9d1d9;
}

.markdown-body h1 { font-size: 28px; border-bottom: 1px solid #1e293b; padding-bottom: 12px; margin-bottom: 24px; color: #f0f6fc; }
.markdown-body h2 { font-size: 22px; margin-top: 32px; margin-bottom: 12px; color: #f0f6fc; }
.markdown-body h3 { font-size: 18px; margin-top: 24px; margin-bottom: 8px; color: #e2e8f0; }
.markdown-body p { margin: 8px 0; }
.markdown-body ul, .markdown-body ol { padding-left: 24px; margin: 8px 0; }
.markdown-body li { margin: 4px 0; }
.markdown-body code { background: #1c2535; padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #00d4ff; }
.markdown-body pre { background: #1c2535; padding: 16px; border-radius: 8px; overflow-x: auto; margin: 12px 0; border: 1px solid #1e293b; }
.markdown-body pre code { background: none; padding: 0; color: #c9d1d9; }
.markdown-body blockquote { border-left: 3px solid #00d4ff; padding: 8px 16px; margin: 12px 0; color: #94a3b8; background: rgba(0,212,255,0.04); border-radius: 0 8px 8px 0; }
.markdown-body table { width: 100%; border-collapse: collapse; margin: 12px 0; }
.markdown-body th, .markdown-body td { padding: 8px 12px; border: 1px solid #1e293b; text-align: left; }
.markdown-body th { background: #1c2535; color: #f0f6fc; font-weight: 600; }
```

- [ ] **Step 5: Verify and commit**

```bash
cd /home/easy/projects/ReqRadar/frontend && npx tsc --noEmit --skipLibCheck 2>&1 | head -20
```

```bash
git add frontend/src/i18n/ frontend/src/components/ErrorBoundary.tsx frontend/src/components/SkeletonCard.tsx frontend/src/components/SkeletonTable.tsx frontend/src/components/SkeletonStat.tsx frontend/src/main.tsx frontend/src/index.css
git commit -m "feat: add i18n foundation, ErrorBoundary, Skeleton components, dark CSS base"
```

---

### Task 2: WebSocket Auto-Reconnect Hook

**Files:**
- Create: `frontend/src/hooks/useWebSocket.ts`

- [ ] **Step 1: Create the hook**

Create `frontend/src/hooks/useWebSocket.ts`:
```typescript
import { useEffect, useRef, useState, useCallback } from 'react';

export type WsStatus = 'connecting' | 'open' | 'closed' | 'reconnecting';

interface UseWebSocketOptions {
  url: string;
  onMessage: (data: unknown) => void;
  enabled?: boolean;
  maxRetries?: number;
}

export function useWebSocket({ url, onMessage, enabled = true, maxRetries = 10 }: UseWebSocketOptions) {
  const [status, setStatus] = useState<WsStatus>('closed');
  const retryCountRef = useRef(0);
  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cleanup = useCallback(() => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
    if (pingTimerRef.current) { clearInterval(pingTimerRef.current); pingTimerRef.current = null; }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!enabled) return;

    cleanup();
    setStatus(retryCountRef.current > 0 ? 'reconnecting' : 'connecting');

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('open');
        retryCountRef.current = 0;

        pingTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage(data);
        } catch {
          // ignore non-JSON
        }
      };

      ws.onerror = () => {
        // handled by onclose
      };

      ws.onclose = () => {
        pingTimerRef.current && clearInterval(pingTimerRef.current);
        setStatus('closed');

        if (retryCountRef.current < maxRetries) {
          retryCountRef.current += 1;
          const delay = Math.min(1000 * Math.pow(2, retryCountRef.current - 1), 30000);
          timerRef.current = setTimeout(connect, delay);
        }
      };
    } catch {
      if (retryCountRef.current < maxRetries) {
        retryCountRef.current += 1;
        timerRef.current = setTimeout(connect, 2000);
      }
    }
  }, [url, enabled, maxRetries, onMessage, cleanup]);

  useEffect(() => {
    if (enabled) {
      connect();
    }
    return cleanup;
  }, [connect, cleanup, enabled]);

  return { status, reconnect: connect };
}
```

- [ ] **Step 2: Verify and commit**

```bash
cd /home/easy/projects/ReqRadar/frontend && npx tsc --noEmit --skipLibCheck frontend/src/hooks/useWebSocket.ts 2>&1 | head -5
```

```bash
git add frontend/src/hooks/useWebSocket.ts
git commit -m "feat: add useWebSocket hook with exponential backoff reconnect"
```

---

### Task 3: AppShell Layout Component

**Files:**
- Create: `frontend/src/components/AppShell.tsx`

- [ ] **Step 1: Create AppShell**

Create `frontend/src/components/AppShell.tsx`:
```tsx
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Button, Dropdown, Avatar, Spin, theme } from 'antd';
import { useAuth } from '../contexts/AuthContext';
import {
  DashboardOutlined,
  ProjectOutlined,
  ExperimentOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons';
import PageLoader from './PageLoader';

const { Header, Content } = Layout;

const navItems = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/projects', icon: <ProjectOutlined />, label: '项目' },
  { key: '/analyses', icon: <ExperimentOutlined />, label: '分析' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
];

export default function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const { token } = theme.useToken();

  if (isLoading) {
    return <PageLoader />;
  }

  if (!isAuthenticated) {
    navigate('/login', { replace: true });
    return <PageLoader />;
  }

  const currentKey = navItems.find(item =>
    item.key === '/'
      ? location.pathname === '/'
      : location.pathname.startsWith(item.key)
  )?.key || '/';

  const userMenu = {
    items: [
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
        danger: true,
      },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === 'logout') logout();
    },
  };

  return (
    <Layout style={{ minHeight: '100vh', background: token.colorBgBase }}>
      <Header
        className="glass"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          height: 56,
          position: 'sticky',
          top: 0,
          zIndex: 100,
          borderBottom: `1px solid ${token.colorBorder}`,
          background: 'rgba(15,22,36,0.85)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}
            onClick={() => navigate('/')}
          >
            <div style={{
              width: 28, height: 28,
              background: 'linear-gradient(135deg, #00d4ff, #7c3aed)',
              borderRadius: 7,
            }} />
            <span style={{ fontWeight: 700, fontSize: 16, color: '#f0f6fc', letterSpacing: -0.3 }}>
              ReqRadar
            </span>
          </div>

          <nav style={{ display: 'flex', gap: 4 }}>
            {navItems.map(item => (
              <Button
                key={item.key}
                type="text"
                icon={item.icon}
                onClick={() => navigate(item.key)}
                style={{
                  color: currentKey === item.key ? token.colorPrimary : token.colorTextSecondary,
                  fontWeight: currentKey === item.key ? 600 : 400,
                  background: currentKey === item.key ? `${token.colorPrimary}15` : 'transparent',
                  borderRadius: 8,
                  height: 36,
                }}
              >
                {item.label}
              </Button>
            ))}
          </nav>
        </div>

        <Dropdown menu={userMenu} placement="bottomRight">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
            <span style={{ fontSize: 13, color: token.colorTextSecondary, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.email || ''}
            </span>
            <Avatar
              size={32}
              icon={<UserOutlined />}
              style={{ background: 'linear-gradient(135deg, #00d4ff, #7c3aed)' }}
            />
          </div>
        </Dropdown>
      </Header>

      <Content style={{ padding: 24, maxWidth: 1280, margin: '0 auto', width: '100%' }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/AppShell.tsx
git commit -m "feat: add AppShell layout with horizontal TopBar, glass effect, sticky header"
```

---

### Task 4: Rewrite App.tsx — New Routing + Theme + ErrorBoundary

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Rewrite App.tsx**

Read the current `frontend/src/App.tsx`, then replace entirely:

```tsx
import { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme as antTheme, App as AntApp } from 'antd';
import { useAuth } from './contexts/AuthContext';
import AppShell from './components/AppShell';
import ErrorBoundary from './components/ErrorBoundary';
import PageLoader from './components/PageLoader';

const Login = lazy(() => import('./pages/Login'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Projects = lazy(() => import('./pages/Projects'));
const ProjectDetail = lazy(() => import('./pages/ProjectDetail'));
const ProjectProfile = lazy(() => import('./pages/ProjectProfile'));
const SynonymManager = lazy(() => import('./pages/SynonymManager'));
const AnalysisList = lazy(() => import('./pages/AnalysisList'));
const AnalysisSubmit = lazy(() => import('./pages/AnalysisSubmit'));
const AnalysisProgress = lazy(() => import('./pages/AnalysisProgress'));
const ReportView = lazy(() => import('./pages/ReportView'));
const LLMConfig = lazy(() => import('./pages/LLMConfig'));
const TemplateManager = lazy(() => import('./pages/TemplateManager'));
const UserPreferences = lazy(() => import('./pages/UserPreferences'));

const darkTheme = {
  algorithm: antTheme.darkAlgorithm,
  token: {
    colorPrimary: '#00d4ff',
    colorBgBase: '#0a0e17',
    colorBgContainer: '#0f1624',
    colorBgElevated: '#161b22',
    colorBorder: '#1e293b',
    colorBorderSecondary: '#1e293b',
    borderRadius: 8,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif",
  },
  components: {
    Layout: {
      headerBg: 'transparent',
      bodyBg: '#0a0e17',
      siderBg: '#0a0e17',
    },
    Card: {
      colorBgContainer: 'rgba(15,22,36,0.7)',
      borderRadiusLG: 12,
      colorBorderSecondary: '#1e293b',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(0,212,255,0.1)',
    },
    Table: {
      colorBgContainer: '#0f1624',
      borderColor: '#1e293b',
      headerBg: '#1c2535',
      rowHoverBg: 'rgba(0,212,255,0.04)',
    },
    Input: {
      colorBgContainer: '#1c2535',
      activeBorderColor: '#00d4ff',
    },
    Select: {
      colorBgContainer: '#1c2535',
      optionSelectedBg: 'rgba(0,212,255,0.12)',
      colorBgElevated: '#161b22',
    },
    Tag: {
      defaultBg: 'rgba(0,212,255,0.08)',
      defaultColor: '#00d4ff',
    },
    Button: {
      primaryShadow: '0 0 0 2px rgba(0,212,255,0.15)',
    },
    Tabs: {
      inkBarColor: '#00d4ff',
      itemActiveColor: '#00d4ff',
      itemSelectedColor: '#00d4ff',
    },
  },
};

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <PageLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <PageLoader />;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ConfigProvider theme={darkTheme}>
      <AntApp>
        <BrowserRouter basename="/app">
          <Suspense fallback={<PageLoader />}>
            <ErrorBoundary>
              <Routes>
                <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />

                <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
                  <Route index element={<Dashboard />} />
                  <Route path="projects" element={<Projects />} />
                  <Route path="projects/:id" element={<ProjectDetail />} />
                  <Route path="projects/:id/profile" element={<ProjectProfile />} />
                  <Route path="projects/:id/synonyms" element={<SynonymManager />} />
                  <Route path="analyses" element={<AnalysisList />} />
                  <Route path="analyses/submit" element={<AnalysisSubmit />} />
                  <Route path="analyses/:id" element={<AnalysisProgress />} />
                  <Route path="reports/:taskId" element={<ReportView />} />
                  <Route path="settings/llm" element={<LLMConfig />} />
                  <Route path="settings/templates" element={<TemplateManager />} />
                  <Route path="settings/preferences" element={<UserPreferences />} />
                </Route>

                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </ErrorBoundary>
          </Suspense>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}
```

- [ ] **Step 2: Verify syntax and commit**

```bash
cd /home/easy/projects/ReqRadar/frontend && npx tsc --noEmit --skipLibCheck 2>&1 | head -20
```

```bash
git add frontend/src/App.tsx
git commit -m "feat: rewrite App.tsx with dark theme, ErrorBoundary, AppShell, new routing"
```

---

### Task 5: AuthContext Fix + Delete Dead Files

**Files:**
- Modify: `frontend/src/contexts/AuthContext.tsx`
- Delete: `frontend/src/AppLayout.tsx`
- Delete: `frontend/src/components/NavMenu.tsx`
- Delete: `frontend/src/pages/SettingsLayout.tsx`
- Delete: `frontend/src/App.css`

- [ ] **Step 1: Fix AuthContext logout**

In `frontend/src/contexts/AuthContext.tsx`, find the `logout` function and replace `window.location.href = '/app/login'` with SPA navigation.

Read the current `AuthContext.tsx` first, then modify the logout function:

Replace the `logout` function body with:
```typescript
  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    setUser(null);
    window.location.href = '/app/login';
  }, []);
```

Note: We keep `window.location.href` for now because AuthContext doesn't have access to `useNavigate` (it's not inside Router). A proper fix with `useNavigate` requires restructuring — deferred to Phase 2. For now, just ensure the token/user are cleared properly.

Also fix the login function to store user info:
```typescript
  const login = useCallback(async (token: string) => {
    localStorage.setItem('access_token', token);
    try {
      const userData = await authApi.getMe();
      setUser(userData);
      localStorage.setItem('user', JSON.stringify(userData));
    } catch {
      // token invalid, clear
      localStorage.removeItem('access_token');
      setUser(null);
    }
  }, []);
```

- [ ] **Step 2: Delete dead files**

```bash
git rm frontend/src/AppLayout.tsx frontend/src/components/NavMenu.tsx frontend/src/pages/SettingsLayout.tsx frontend/src/App.css
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/contexts/AuthContext.tsx && git add -u && git commit -m "refactor: fix AuthContext, delete AppLayout/NavMenu/SettingsLayout/App.css dead code"
```

---

### Task 6: Dashboard Page

**Files:**
- Create: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Create Dashboard**

Create `frontend/src/pages/Dashboard.tsx`:

Read the current `frontend/src/api/projects.ts` and `frontend/src/api/profile.ts` first to understand the API shapes, then write:

```tsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, Typography, Button, Empty, List, Tag, Space } from 'antd';
import {
  ProjectOutlined, TagsOutlined, AppstoreOutlined,
  ExclamationCircleOutlined, PlusOutlined, ExperimentOutlined,
  FileTextOutlined, SettingOutlined,
} from '@ant-design/icons';
import { projectsApi } from '../api/projects';
import { profileApi } from '../api/profile';
import SkeletonStat from '../components/SkeletonStat';

const { Title, Text } = Typography;

interface ProjectSummary {
  id: number;
  name: string;
  termsCount: number;
  modulesCount: number;
  pendingChangesCount: number;
  recentChangelog: string;
  updatedAt: string;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const projectsData = await projectsApi.getProjects();
        const summaries: ProjectSummary[] = [];

        for (const p of projectsData) {
          try {
            const [memory, profile] = await Promise.allSettled([
              projectsApi.getProjectMemory(p.id),
              profileApi.getProfile(p.id),
            ]);

            const termsCount = memory.status === 'fulfilled' && memory.value?.terms
              ? (Array.isArray(memory.value.terms) ? memory.value.terms.length : 0)
              : 0;
            const modulesCount = memory.status === 'fulfilled' && memory.value?.modules
              ? (Array.isArray(memory.value.modules) ? memory.value.modules.length : 0)
              : 0;
            const pendingChangesCount = profile.status === 'fulfilled' && profile.value?.pending_changes
              ? (Array.isArray(profile.value.pending_changes) ? profile.value.pending_changes.length : 0)
              : 0;

            summaries.push({
              id: p.id,
              name: p.name,
              termsCount,
              modulesCount,
              pendingChangesCount,
              recentChangelog: '',
              updatedAt: p.updated_at || p.created_at || '',
            });
          } catch {
            summaries.push({
              id: p.id, name: p.name,
              termsCount: 0, modulesCount: 0, pendingChangesCount: 0,
              recentChangelog: '', updatedAt: p.updated_at || '',
            });
          }
        }
        setProjects(summaries);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const totalTerms = projects.reduce((sum, p) => sum + p.termsCount, 0);
  const totalModules = projects.reduce((sum, p) => sum + p.modulesCount, 0);
  const totalPending = projects.reduce((sum, p) => sum + p.pendingChangesCount, 0);

  if (loading) {
    return (
      <div>
        <SkeletonStat count={4} />
        <div style={{ marginTop: 24 }}>
          <div style={{ padding: 32, background: 'rgba(15,22,36,0.7)', borderRadius: 12, border: '1px solid #1e293b' }}>
            <SkeletonStat count={3} />
          </div>
        </div>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 20px' }}>
        <ProjectOutlined style={{ fontSize: 64, color: '#1e293b', marginBottom: 16 }} />
        <Title level={3} style={{ color: '#94a3b8' }}>还没有项目</Title>
        <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
          创建第一个项目开始使用需求分析
        </Text>
        <Button type="primary" icon={<PlusOutlined />} size="large" onClick={() => navigate('/projects')}>
          新建项目
        </Button>
      </div>
    );
  }

  return (
    <div>
      <Title level={3} style={{ color: '#f0f6fc', marginBottom: 4 }}>
        欢迎回来
      </Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        知识库总览
      </Text>

      {error && (
        <Text type="warning" style={{ display: 'block', marginBottom: 16 }}>
          部分数据加载失败
        </Text>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="glass-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <ProjectOutlined style={{ fontSize: 22, color: '#00d4ff' }} />
              <div>
                <div style={{ fontSize: 12, color: '#64748b' }}>项目</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#f0f6fc' }}>{projects.length}</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="glass-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <TagsOutlined style={{ fontSize: 22, color: '#7c3aed' }} />
              <div>
                <div style={{ fontSize: 12, color: '#64748b' }}>术语</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#f0f6fc' }}>{totalTerms}</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="glass-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <AppstoreOutlined style={{ fontSize: 22, color: '#10b981' }} />
              <div>
                <div style={{ fontSize: 12, color: '#64748b' }}>模块</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#f0f6fc' }}>{totalModules}</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="glass-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <ExclamationCircleOutlined style={{ fontSize: 22, color: '#f59e0b' }} />
              <div>
                <div style={{ fontSize: 12, color: '#64748b' }}>待确认</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#f0f6fc' }}>{totalPending}</div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="项目总览" className="glass-card" style={{ marginBottom: 24 }}>
        <List
          dataSource={projects}
          renderItem={(item) => (
            <List.Item
              style={{ cursor: 'pointer', borderBottom: '1px solid #1e293b', padding: '12px 0' }}
              onClick={() => navigate(`/projects/${item.id}`)}
            >
              <List.Item.Meta
                title={<span style={{ color: '#e2e8f0' }}>{item.name}</span>}
                description={
                  <Space size="middle">
                    <Tag color="blue">{item.termsCount} 术语</Tag>
                    <Tag color="green">{item.modulesCount} 模块</Tag>
                    {item.pendingChangesCount > 0 && (
                      <Tag color="orange">{item.pendingChangesCount} 待确认</Tag>
                    )}
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Card>

      <Card title="快捷操作" className="glass-card">
        <Space size="middle" wrap>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/projects')}>
            新建项目
          </Button>
          <Button icon={<ExperimentOutlined />} onClick={() => navigate('/analyses/submit')}>
            提交分析
          </Button>
          <Button icon={<FileTextOutlined />} onClick={() => navigate('/settings/templates')}>
            管理模板
          </Button>
          <Button icon={<SettingOutlined />} onClick={() => navigate('/settings/llm')}>
            配置 LLM
          </Button>
        </Space>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Verify and commit**

```bash
cd /home/easy/projects/ReqRadar/frontend && npx tsc --noEmit --skipLibCheck 2>&1 | head -20
```

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: add knowledge-oriented Dashboard with stats and project overview"
```

---

### Task 7: Page Adaptations Batch — Login, Projects, ProjectDetail, ProjectProfile

**Files:**
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/pages/Projects.tsx`
- Modify: `frontend/src/pages/ProjectDetail.tsx`
- Modify: `frontend/src/pages/ProjectProfile.tsx`

- [ ] **Step 1: Fix Login.tsx**

Read current `frontend/src/pages/Login.tsx`, then make these changes:

1. Separate loading state for login and register:
   - Replace single `loading` state with `loginLoading` and `registerLoading`
   - Each submit button shows its own spinner

2. Show backend error details:
   - In the `catch` blocks, extract error message from caught error (e.g., `e.response?.data?.detail` or `e.message`)
   - Show it in the `message.error()` call instead of generic text

3. Don't change any layout or Ant Design components — just fix the logic.

- [ ] **Step 2: Fix Projects.tsx — add delete + search**

Read current `frontend/src/pages/Projects.tsx`, then add:

1. Search bar at top:
```tsx
<Input.Search
  placeholder="搜索项目..."
  allowClear
  onChange={(e) => setSearchText(e.target.value)}
  style={{ marginBottom: 16, maxWidth: 400 }}
/>
```

2. Filter projects: `const filtered = projects.filter(p => p.name.toLowerCase().includes(searchText.toLowerCase()))`

3. Delete button on each card (next to existing action buttons):
```tsx
<Button
  size="small"
  danger
  icon={<DeleteOutlined />}
  onClick={(e) => {
    e.stopPropagation();
    Modal.confirm({
      title: '删除项目',
      content: '确定要删除这个项目吗？此操作不可撤销。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await projectsApi.deleteProject(project.id);
          message.success('项目已删除');
          fetchProjects();
        } catch {
          message.error('删除失败');
        }
      },
    });
  }}
/>
```

Add imports: `import { Modal, Input } from 'antd'; import { DeleteOutlined, SearchOutlined } from '@ant-design/icons';`

- [ ] **Step 3: Fix ProjectDetail.tsx — add delete + submit analysis CTA**

Read current `frontend/src/pages/ProjectDetail.tsx`, then add:

1. Delete button next to the edit button in the header area:
```tsx
<Button danger icon={<DeleteOutlined />} onClick={handleDelete}>删除项目</Button>
```
Implement `handleDelete` with `Modal.confirm` + `projectsApi.deleteProject` + `navigate('/projects')`.

2. Submit analysis CTA button:
```tsx
<Button type="primary" icon={<ExperimentOutlined />} onClick={() => navigate(`/analyses/submit?projectId=${project.id}`)}>
  提交需求分析
</Button>
```

Add imports: `import { DeleteOutlined, ExperimentOutlined } from '@ant-design/icons'; import { Modal } from 'antd';`

- [ ] **Step 4: Fix ProjectProfile.tsx — show all fields**

Read current `frontend/src/pages/ProjectProfile.tsx`. Currently only shows `description` field. Add display/edit for:

```tsx
<Form.Item label="架构风格" name="architecture_style">
  <Input.TextArea rows={2} />
</Form.Item>
<Form.Item label="技术栈" name="tech_stack">
  <Input.TextArea rows={3} placeholder="JSON 格式: {\"frontend\": [\"React\"], \"backend\": [\"Python\"]}" />
</Form.Item>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Login.tsx frontend/src/pages/Projects.tsx frontend/src/pages/ProjectDetail.tsx frontend/src/pages/ProjectProfile.tsx
git commit -m "feat: improve Login/Projects/ProjectDetail/ProjectProfile pages"
```

---

### Task 8: Page Adaptations Batch — Analysis Pages + ReportView + LLMConfig

**Files:**
- Modify: `frontend/src/pages/AnalysisSubmit.tsx`
- Modify: `frontend/src/pages/AnalysisProgress.tsx`
- Modify: `frontend/src/pages/ReportView.tsx`
- Modify: `frontend/src/pages/LLMConfig.tsx`

- [ ] **Step 1: Fix AnalysisSubmit.tsx — Tab state preservation**

Read current `frontend/src/pages/AnalysisSubmit.tsx`. The issue: switching tabs loses depth/template/focus state. Fix:

1. Move `depth`, `templateId`, `focusAreas` state into a shared parent that persists across tab switches:
```tsx
const [depth, setDepth] = useState('standard');
const [templateId, setTemplateId] = useState<number | undefined>();
const [focusAreas, setFocusAreas] = useState<string[]>([]);
```

2. Pass them as props to both tabs' forms. Don't reset on tab change.

3. The `handleFileUpload` function should also include `depth`, `templateId`, `focusAreas` in the API call (check if `uploadAnalysis` API supports them; if not, just include depth at minimum).

- [ ] **Step 2: Fix AnalysisProgress.tsx — useWebSocket**

Read current `frontend/src/pages/AnalysisProgress.tsx`. Replace the raw WebSocket logic with the `useWebSocket` hook:

```tsx
import { useWebSocket } from '../hooks/useWebSocket';

// Inside component:
const taskId = id ? Number(id) : 0;
const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/analysis/${taskId}`;

const { status: wsStatus } = useWebSocket({
  url: wsUrl,
  enabled: !!taskId,
  onMessage: (data: any) => {
    // existing message handling logic
    switch (data.type) {
      case 'dimension_progress': setDimensionStatus(data.dimensions || {}); break;
      case 'analysis_complete': setComplete(true); break;
      case 'analysis_failed': setFailed(true); break;
      case 'agent_thinking': setThinkingMessage(data.message); break;
      // ... etc
    }
  },
});

// Show connection status indicator
<Text type="secondary" style={{ fontSize: 12 }}>
  连接状态: {wsStatus === 'open' ? '🟢 已连接' : wsStatus === 'reconnecting' ? '🟡 重连中' : '🔴 断开'}
</Text>
```

Remove the manual WebSocket `useEffect` code. Keep all the `onMessage` handler logic.

- [ ] **Step 3: Fix ReportView.tsx — TOC scrollIntoView**

Read current `frontend/src/pages/ReportView.tsx`. Replace the Anchor component's onClick:

```tsx
<Anchor
  items={[
    { key: 'summary', href: '#summary', title: '摘要' },
    { key: 'findings', href: '#findings', title: '发现' },
    { key: 'recommendations', href: '#recommendations', title: '建议' },
  ]}
  onClick={(e, link) => {
    e.preventDefault();
    const el = document.getElementById(link.href.split('#')[1]);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }}
/>
```

- [ ] **Step 4: Fix LLMConfig.tsx — add test connection button**

Read current `frontend/src/pages/LLMConfig.tsx`. Add a test connection button next to the LLM model field:

```tsx
<Button
  size="small"
  loading={testLoading}
  onClick={async () => {
    setTestLoading(true);
    try {
      // Simple API call to test connectivity
      const resp = await fetch('/api/configs/test-llm', { method: 'POST' });
      if (resp.ok) {
        message.success('连接测试成功');
      } else {
        message.error('连接测试失败');
      }
    } catch {
      message.error('无法连接到服务器');
    } finally {
      setTestLoading(false);
    }
  }}
>
  测试连接
</Button>
```

Add state: `const [testLoading, setTestLoading] = useState(false);`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AnalysisSubmit.tsx frontend/src/pages/AnalysisProgress.tsx frontend/src/pages/ReportView.tsx frontend/src/pages/LLMConfig.tsx
git commit -m "feat: fix AnalysisSubmit tabs, WebSocket reconnect, ReportView TOC, LLM test button"
```

---

### Task 9: Build & Verify

**Files:** None

- [ ] **Step 1: TypeScript check**

```bash
cd /home/easy/projects/ReqRadar/frontend && npx tsc --noEmit --skipLibCheck 2>&1
```

Fix any compilation errors. Expected: no errors (or only pre-existing ones).

- [ ] **Step 2: Build**

```bash
cd /home/easy/projects/ReqRadar/frontend && npm run build 2>&1
```

Expected: successful build with no errors.

- [ ] **Step 3: Check all imports work**

```bash
cd /home/easy/projects/ReqRadar/frontend && npx vite build --mode development 2>&1 | tail -5
```

- [ ] **Step 4: Update backend's static dir if needed**

Check if the Vite build output goes to the correct path for the backend to serve:
```bash
ls frontend/dist/ | head -5
```

The output should go to `../src/reqradar/web/static/` (based on Vite config `outDir`). If the config is correct, the build output will be there automatically.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: final build verification, fix remaining TS errors"
```
