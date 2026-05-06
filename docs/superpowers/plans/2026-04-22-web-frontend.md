# ReqRadar Web 前端开发计划

**Goal:** 为 ReqRadar 构建浏览器端操作界面，使非技术团队成员能够通过网页提交需求分析、实时查看执行进度、在线浏览分析报告，降低使用门槛。

**Architecture:** React 18 + TypeScript + Vite 构建工具链，Ant Design 5 作为 UI 组件库，React Router 处理客户端路由，Axios 处理 HTTP 通信，原生 WebSocket 处理实时进度推送。生产构建产物由 FastAPI 作为静态文件托管，实现单进程部署。

**Tech Stack:** React 18, TypeScript 5, Vite 5, Ant Design 5, React Router 6, Axios, react-markdown (报告渲染)

---

## 一、前端架构设计

### 1.1 项目结构

```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/
│   ├── main.tsx                 # 应用入口
│   ├── App.tsx                  # 根组件，路由配置
│   ├── index.css                # 全局样式 + 暗色主题变量
│   ├── api/
│   │   ├── client.ts            # Axios 实例 + 拦截器
│   │   ├── auth.ts              # 认证相关 API
│   │   ├── projects.ts          # 项目相关 API
│   │   ├── analyses.ts          # 分析任务相关 API
│   │   ├── reports.ts           # 报告相关 API
│   │   └── memory.ts            # 项目记忆相关 API
│   ├── types/
│   │   ├── api.ts               # 后端 API 返回的 TypeScript 类型
│   │   └── websocket.ts         # WebSocket 消息类型
│   ├── hooks/
│   │   ├── useAuth.ts           # 认证状态管理
│   │   ├── useWebSocket.ts      # WebSocket 连接封装
│   │   └── useAnalysisProgress.ts  # 分析进度状态
│   ├── context/
│   │   └── AuthContext.tsx      # 全局认证上下文
│   ├── layouts/
│   │   └── AppLayout.tsx        # 主布局（侧边栏 + 头部 + 内容区）
│   ├── pages/
│   │   ├── Login.tsx            # 登录/注册页面
│   │   ├── Projects.tsx         # 项目列表页面
│   │   ├── ProjectDetail.tsx    # 项目详情页（记忆、设置）
│   │   ├── AnalysisSubmit.tsx   # 提交分析任务
│   │   ├── AnalysisList.tsx     # 分析任务列表
│   │   ├── AnalysisProgress.tsx # 实时进度页面
│   │   └── ReportView.tsx       # 报告查看页面
│   └── components/
│       ├── StepProgress.tsx     # 6步流程进度条
│       ├── RiskBadge.tsx        # 风险等级标签
│       ├── ProjectCard.tsx      # 项目卡片
│       ├── AnalysisTaskCard.tsx # 分析任务卡片
│       ├── ReportTOC.tsx        # 报告目录导航
│       ├── FileUploader.tsx     # 文件上传组件
│       ├── MemoryTermTable.tsx  # 术语表组件
│       ├── MemoryModuleTable.tsx# 模块列表组件
│       └── NavMenu.tsx          # 导航菜单
```

### 1.2 与后端的集成方式

**开发模式**：Vite dev server 代理 API 请求到后端
```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/ws': { target: 'ws://localhost:8000', ws: true },
  },
}
```

**生产模式**：`npm run build` 输出到 `src/reqradar/web/static/`，FastAPI `StaticFiles` 托管
```typescript
// vite.config.ts
build: {
  outDir: '../src/reqradar/web/static',
  emptyOutDir: true,
}
```

**API Base URL**：开发时通过 proxy 走相对路径 `/api`，生产时同为相对路径（前后端同域名）

---

## 二、类型定义（与后端 API 对齐）

### 2.1 API 响应类型

```typescript
// src/types/api.ts

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: 'admin' | 'editor' | 'viewer';
}

export interface Project {
  id: number;
  name: string;
  description: string;
  repo_path: string;
  docs_path: string;
  index_path: string;
  config_json: string;
  created_at: string;
  updated_at: string;
}

export interface AnalysisTask {
  id: number;
  project_id: number;
  requirement_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  error_message: string;
  step_summary?: Record<string, { success: boolean; error?: string }>;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface Report {
  id: number;
  task_id: number;
  content_markdown: string;
  content_html: string;
  risk_level?: string;
  created_at: string;
}

export interface TermDefinition {
  term: string;
  definition: string;
  domain: string;
}

export interface ModuleInfo {
  name: string;
  responsibility: string;
  key_classes: string[];
  code_summary: string;
}
```

### 2.2 WebSocket 消息类型

```typescript
// src/types/websocket.ts

export type WSMessageType = 
  | 'step_start' 
  | 'step_complete' 
  | 'step_progress'
  | 'analysis_complete' 
  | 'analysis_failed';

export interface WSMessage {
  type: WSMessageType;
  step?: string;
  description?: string;
  success?: boolean;
  error?: string;
  tool_call?: string;
  round?: number;
  task_id?: number;
}

export type StepStatus = 'wait' | 'process' | 'finish' | 'error';

export const STEP_NAMES = ['read', 'extract', 'map_keywords', 'retrieve', 'analyze', 'generate'] as const;
export const STEP_LABELS = ['读取', '提取', '映射', '检索', '分析', '生成'] as const;
```

---

## 三、页面设计与路由

### 3.1 路由表

| 路径 | 页面 | 鉴权 | 说明 |
|------|------|------|------|
| `/login` | Login | 无 | 登录/注册切换 |
| `/` | Projects | JWT | 项目列表（首页） |
| `/projects/:id` | ProjectDetail | JWT | 项目详情 + 记忆 + 设置 |
| `/projects/:id/analyze` | AnalysisSubmit | JWT | 提交分析（文本/文件） |
| `/analyses` | AnalysisList | JWT | 全部分析任务列表 |
| `/analyses/:id` | AnalysisProgress | JWT | 实时进度（WebSocket） |
| `/analyses/:id/report` | ReportView | JWT | 报告查看 |

未登录用户访问受保护路由 → 重定向到 `/login`
已登录用户访问 `/login` → 重定向到 `/`

### 3.2 页面详细设计

#### Login 页面 (`/login`)

- 左侧：品牌区域（ReqRadar Logo + 标语"需求透视"）
- 右侧：登录/注册表单（Ant Design Tabs 切换）
- 登录表单：邮箱、密码、记住我
- 注册表单：邮箱、密码、确认密码、显示名称
- 提交后保存 token 到 localStorage，跳转首页

#### Projects 页面 (`/`)

- 页面标题"项目列表" + 新建项目按钮
- 项目卡片网格（Ant Design Card）
- 每个卡片显示：项目名称、描述、创建时间、索引状态标签
- 点击卡片进入 ProjectDetail
- 空状态：引导用户创建第一个项目

#### ProjectDetail 页面 (`/projects/:id`)

- 顶部：项目名称 + 描述 + 操作按钮（编辑、删除、触发索引）
- Tabs 切换：
  - **概览**：项目信息、索引状态、最近分析
  - **记忆**：术语表（只读）、模块列表（只读）、团队信息（只读）
  - **设置**：项目配置编辑
- 底部："提交分析"按钮，跳转到 `/projects/:id/analyze`

#### AnalysisSubmit 页面 (`/projects/:id/analyze`)

- 两步表单（Ant Design Steps）：
  1. **选择输入方式**：文本输入 / 文件上传
     - 文本输入：TextArea，支持粘贴
     - 文件上传：拖拽区域，支持 Markdown/PDF/DOCX（Ant Design Upload）
  2. **确认提交**：显示需求名称（可编辑）、预览文本前 200 字
- 提交后跳转到 AnalysisProgress 页面

#### AnalysisList 页面 (`/analyses`)

- 筛选栏：项目选择器、状态筛选器、时间范围
- 表格（Ant Design Table）：
  - 列：需求名称、项目、状态、风险等级、提交时间、耗时
  - 状态列带颜色标签（pending 灰、running 蓝、completed 绿、failed 红）
  - 风险等级列使用 RiskBadge 组件
  - 操作列：查看报告（completed）、查看进度（running/pending）、重试（failed）
- 排序：默认按时间倒序

#### AnalysisProgress 页面 (`/analyses/:id`)

- 左侧：StepProgress 组件（大版本，占据主要区域）
- 右侧：任务信息面板
  - 需求名称
  - 提交时间
  - 当前步骤描述
  - 已用时间（定时器）
- WebSocket 连接状态指示器
- 分析完成后自动跳转到 ReportView
- 分析失败显示错误信息和重试按钮

#### ReportView 页面 (`/analyses/:id/report`)

- 左侧：ReportTOC 目录导航（固定定位）
- 右侧：报告内容渲染
  - 使用 `react-markdown` 渲染 Markdown
  - 代码块高亮（prismjs 或 highlight.js）
  - 影响模块路径可点击（跳转外部代码仓库）
  - 风险等级标签使用颜色
- 顶部操作栏：
  - 下载 Markdown 按钮
  - 返回分析列表按钮
  - 报告元信息（生成时间、风险等级）

---

## 四、核心组件设计

### 4.1 StepProgress 组件

```typescript
interface StepProgressProps {
  taskId: number;
  onComplete?: () => void;
  onFailed?: (error: string) => void;
}
```

功能：
- 建立 WebSocket 连接（`useWebSocket` hook）
- 监听 step_start / step_complete / analysis_complete / analysis_failed 事件
- 使用 Ant Design Steps 组件显示 6 步状态
- 每个步骤显示：名称、状态图标、耗时（计算得出）
- 支持大版本（页面居中）和小版本（卡片内紧凑显示）

### 4.2 RiskBadge 组件

```typescript
interface RiskBadgeProps {
  level: 'low' | 'medium' | 'high' | 'critical' | string;
}
```

颜色映射：
- low → 绿色（success）
- medium → 黄色（warning）
- high → 橙色（orange）
- critical → 红色（error）
- unknown → 灰色（default）

### 4.3 FileUploader 组件

```typescript
interface FileUploaderProps {
  onUpload: (file: File) => void;
  accept?: string;  // 默认 '.md,.pdf,.docx,.txt'
  maxSize?: number; // 默认 10MB
}
```

功能：
- 拖拽上传区域
- 文件类型校验
- 文件大小校验
- 上传进度显示（模拟，实际后端接收整文件后处理）

### 4.4 ReportTOC 组件

功能：
- 解析 Markdown 内容中的标题（# ## ###）
- 生成目录树
- 点击滚动到对应位置（锚点跳转）
- 当前阅读位置高亮（IntersectionObserver）

### 4.5 NavMenu 组件

功能：
- 侧边栏导航（Ant Design Menu）
- 项目：项目列表、分析任务列表
- 用户：个人信息、退出登录
- 底部：版本号、暗色主题切换按钮

---

## 五、状态管理

### 5.1 全局状态（React Context）

**AuthContext**：
```typescript
interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
}
```

初始化时从 localStorage 读取 token，调用 `/api/auth/me` 恢复用户状态。

### 5.2 局部状态（useState / useReducer）

- **AnalysisProgress 页面**：WebSocket 消息队列、步骤状态映射
- **AnalysisList 页面**：筛选条件、分页参数
- **ReportView 页面**：当前阅读章节（用于 TOC 高亮）

### 5.3 服务端状态（Axios + SWR 模式）

不使用 React Query（减少依赖），使用自定义 hook + Axios：

```typescript
// hooks/useProjects.ts
export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    api.get('/api/projects').then(res => {
      setProjects(res.data);
      setLoading(false);
    });
  }, []);
  
  return { projects, loading, refresh: () => {...} };
}
```

---

## 六、API 客户端设计

### 6.1 Axios 实例配置

```typescript
// src/api/client.ts
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

// 请求拦截器：附加 JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('reqradar_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：401 时清除 token 并跳转登录
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('reqradar_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;
```

### 6.2 API 模块封装

```typescript
// src/api/auth.ts
import api from './client';

export const authApi = {
  register: (data: { email: string; password: string; display_name: string }) =>
    api.post('/auth/register', data),
  login: (data: { email: string; password: string }) =>
    api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
};

// src/api/projects.ts
export const projectsApi = {
  list: () => api.get('/projects'),
  create: (data: Partial<Project>) => api.post('/projects', data),
  get: (id: number) => api.get(`/projects/${id}`),
  update: (id: number, data: Partial<Project>) => api.put(`/projects/${id}`, data),
  index: (id: number) => api.post(`/projects/${id}/index`),
  terminology: (id: number) => api.get(`/projects/${id}/terminology`),
  modules: (id: number) => api.get(`/projects/${id}/modules`),
  team: (id: number) => api.get(`/projects/${id}/team`),
  history: (id: number) => api.get(`/projects/${id}/history`),
};

// src/api/analyses.ts
export const analysesApi = {
  submit: (data: { project_id: number; requirement_name?: string; requirement_text: string }) =>
    api.post('/analyses', data),
  upload: (formData: FormData) =>
    api.post('/analyses/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  list: (params?: { project_id?: number; status?: string }) =>
    api.get('/analyses', { params }),
  get: (id: number) => api.get(`/analyses/${id}`),
  retry: (id: number) => api.post(`/analyses/${id}/retry`),
};

// src/api/reports.ts
export const reportsApi = {
  get: (taskId: number) => api.get(`/reports/${taskId}`),
  downloadMarkdown: (taskId: number) =>
    api.get(`/reports/${taskId}/markdown`, { responseType: 'blob' }),
  getHtml: (taskId: number) => api.get(`/reports/${taskId}/html`),
};
```

---

## 七、WebSocket 集成

### 7.1 useWebSocket Hook

```typescript
// hooks/useWebSocket.ts
export function useWebSocket(taskId: number) {
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<WSMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('reqradar_token');
    const ws = new WebSocket(`/api/analyses/${taskId}/ws?token=${token}`);
    
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data);
      setMessages(prev => [...prev, msg]);
    };
    
    wsRef.current = ws;
    return () => ws.close();
  }, [taskId]);

  return { connected, messages };
}
```

### 7.2 useAnalysisProgress Hook

```typescript
// hooks/useAnalysisProgress.ts
export function useAnalysisProgress(taskId: number) {
  const { connected, messages } = useWebSocket(taskId);
  const [stepStatuses, setStepStatuses] = useState<Record<string, StepStatus>>({});
  const [isComplete, setIsComplete] = useState(false);
  const [isFailed, setIsFailed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    for (const msg of messages) {
      switch (msg.type) {
        case 'step_start':
          setStepStatuses(prev => ({ ...prev, [msg.step!]: 'process' }));
          break;
        case 'step_complete':
          setStepStatuses(prev => ({ 
            ...prev, 
            [msg.step!]: msg.success ? 'finish' : 'error' 
          }));
          break;
        case 'analysis_complete':
          setIsComplete(true);
          break;
        case 'analysis_failed':
          setIsFailed(true);
          setError(msg.error || '分析失败');
          break;
      }
    }
  }, [messages]);

  return { connected, stepStatuses, isComplete, isFailed, error };
}
```

---

## 八、主题与样式

### 8.1 暗色主题支持

Ant Design 5 内置暗色主题，通过 ConfigProvider 切换：

```typescript
// App.tsx
import { ConfigProvider, theme } from 'antd';

function App() {
  const [isDark, setIsDark] = useState(() => 
    localStorage.getItem('theme') === 'dark'
  );

  return (
    <ConfigProvider
      theme={{
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
      }}
    >
      {/* ... */}
    </ConfigProvider>
  );
}
```

### 8.2 响应式断点

| 断点 | 宽度 | 布局调整 |
|------|------|---------|
| xs | < 576px | 单列，侧边栏收起为抽屉 |
| sm | 576-768px | 单列，侧边栏收起 |
| md | 768-992px | 双列，侧边栏固定 |
| lg | 992-1200px | 三列网格 |
| xl | > 1200px | 最大内容宽度 1200px 居中 |

移动端适配重点：
- 侧边栏变为抽屉式（Ant Design Drawer）
- 表格横向滚动
- 报告页面 TOC 变为顶部折叠面板

---

## 九、开发阶段和任务拆解

### Task 1：项目初始化和基础架构

**文件：**
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/index.css`
- `frontend/src/App.tsx`

**步骤：**
1. `npm create vite@latest frontend -- --template react-ts`
2. `cd frontend && npm install antd @ant-design/icons react-router-dom axios react-markdown`
3. `npm install -D @types/node`
4. 配置 `vite.config.ts`（proxy + build outDir）
5. 配置 `tsconfig.json`（paths 别名 `@/` → `./src/`）
6. 编写 `main.tsx`（StrictMode + ConfigProvider）
7. 编写 `App.tsx`（路由配置 + AuthProvider 包裹）
8. 编写全局样式（暗色主题 CSS 变量）

**验证：**
```bash
cd frontend && npm run dev
```
访问 `http://localhost:5173` 应显示空白页面（无报错）

### Task 2：认证模块（Login + AuthContext）

**文件：**
- `frontend/src/api/client.ts`
- `frontend/src/api/auth.ts`
- `frontend/src/context/AuthContext.tsx`
- `frontend/src/hooks/useAuth.ts`
- `frontend/src/pages/Login.tsx`

**步骤：**
1. 创建 Axios client（拦截器配置）
2. 创建 AuthContext（全局认证状态）
3. 创建 Login 页面（表单 + Tabs 切换登录/注册）
4. 实现登录/注册 API 调用
5. 实现路由守卫（未登录重定向）

**验证：**
- 后端需先启动并运行（Task 3 完成后）
- 注册新用户 → 成功
- 登录 → token 存入 localStorage
- 刷新页面 → 自动恢复登录状态

### Task 3：布局组件和导航

**文件：**
- `frontend/src/layouts/AppLayout.tsx`
- `frontend/src/components/NavMenu.tsx`

**步骤：**
1. AppLayout：侧边栏 + 头部 + 内容区结构
2. NavMenu：导航菜单（项目列表、分析任务）
3. 用户头像下拉菜单（个人信息、退出、主题切换）
4. 面包屑导航（可选）

### Task 4：项目列表和详情

**文件：**
- `frontend/src/api/projects.ts`
- `frontend/src/pages/Projects.tsx`
- `frontend/src/pages/ProjectDetail.tsx`
- `frontend/src/components/ProjectCard.tsx`

**步骤：**
1. Projects 页面：卡片网格布局 + 新建项目模态框
2. ProjectCard 组件：名称、描述、时间、状态标签
3. ProjectDetail 页面：Tabs（概览、记忆、设置）
4. 记忆 Tab：术语表、模块列表（只读表格）

**API 依赖：** `/api/projects`, `/api/projects/:id`, `/api/projects/:id/terminology`, `/api/projects/:id/modules`

### Task 5：分析任务提交

**文件：**
- `frontend/src/pages/AnalysisSubmit.tsx`
- `frontend/src/components/FileUploader.tsx`
- `frontend/src/api/analyses.ts`

**步骤：**
1. AnalysisSubmit 页面：两步表单（选择输入方式 → 确认提交）
2. FileUploader 组件：拖拽上传 + 文件校验
3. 文本输入模式：TextArea + 需求名称输入
4. 提交后跳转到 AnalysisProgress 页面

**API 依赖：** `/api/analyses`, `/api/analyses/upload`

### Task 6：实时进度页面（WebSocket）

**文件：**
- `frontend/src/hooks/useWebSocket.ts`
- `frontend/src/hooks/useAnalysisProgress.ts`
- `frontend/src/pages/AnalysisProgress.tsx`
- `frontend/src/components/StepProgress.tsx`

**步骤：**
1. useWebSocket hook：建立连接、消息收集、重连逻辑
2. useAnalysisProgress hook：消息解析为步骤状态
3. StepProgress 组件：Ant Design Steps + 状态映射
4. AnalysisProgress 页面：StepProgress + 任务信息面板 + 自动跳转

**关键交互：**
- 分析完成 → 自动跳转到 ReportView（`navigate(`/analyses/${taskId}/report`)`）
- 分析失败 → 显示错误 + 重试按钮

### Task 7：分析任务列表

**文件：**
- `frontend/src/pages/AnalysisList.tsx`
- `frontend/src/components/AnalysisTaskCard.tsx` 或表格
- `frontend/src/components/RiskBadge.tsx`

**步骤：**
1. AnalysisList 页面：筛选栏 + 表格
2. 表格列：需求名称、项目、状态、风险等级、时间、操作
3. RiskBadge 组件：颜色映射
4. 操作按钮：查看报告、查看进度、重试

### Task 8：报告查看页面

**文件：**
- `frontend/src/pages/ReportView.tsx`
- `frontend/src/components/ReportTOC.tsx`
- `frontend/src/api/reports.ts`

**步骤：**
1. ReportView 页面：左右布局（TOC + 内容）
2. 使用 react-markdown 渲染 Markdown
3. ReportTOC：解析标题生成目录 + 锚点跳转
4. 顶部操作栏：下载 Markdown、返回
5. 代码块高亮（react-markdown 插件）

**API 依赖：** `/api/reports/:task_id`

### Task 9：构建和集成验证

**步骤：**
1. `npm run build`（输出到 `src/reqradar/web/static/`）
2. 启动后端：`PYTHONPATH=src reqradar serve`
3. 访问 `http://localhost:8000` 测试完整流程
4. 验证：注册 → 创建项目 → 提交分析 → 查看进度 → 查看报告

### Task 10：Docker 集成（前端构建）

**步骤：**
1. Dockerfile 中添加 Node.js 构建阶段
2. `docker-compose.yml` 保持单服务
3. 验证 Docker 构建后前端静态文件正确生成

---

## 十、前端工作量估算

| Task | 内容 | 预估 |
|------|------|------|
| 1 | 项目初始化 + Vite 配置 | 0.5 天 |
| 2 | 认证模块（Login + AuthContext） | 1 天 |
| 3 | 布局 + 导航 | 0.5 天 |
| 4 | 项目列表 + 详情 | 1.5 天 |
| 5 | 分析任务提交 | 1 天 |
| 6 | 实时进度（WebSocket） | 1.5 天 |
| 7 | 分析任务列表 | 1 天 |
| 8 | 报告查看 | 1.5 天 |
| 9 | 构建 + 集成验证 | 1 天 |
| 10 | Docker 集成 | 0.5 天 |
| **总计** | | **约 10 天** |

---

## 十一、前后端协作检查清单

| 前端需求 | 后端 API | 状态 |
|---------|---------|------|
| 用户注册/登录 | `/api/auth/register`, `/api/auth/login` | 已定义 |
| 获取当前用户 | `/api/auth/me` | 已定义 |
| 项目列表 | `/api/projects` GET | 已定义 |
| 创建项目 | `/api/projects` POST | 已定义 |
| 项目详情 | `/api/projects/:id` GET | 已定义 |
| 术语表 | `/api/projects/:id/terminology` GET | 已定义 |
| 模块列表 | `/api/projects/:id/modules` GET | 已定义 |
| 提交分析（文本） | `/api/analyses` POST | 已定义 |
| 提交分析（文件） | `/api/analyses/upload` POST | 已定义 |
| 分析列表 | `/api/analyses` GET | 已定义 |
| 分析详情 | `/api/analyses/:id` GET | 已定义 |
| 重试分析 | `/api/analyses/:id/retry` POST | 已定义 |
| WebSocket 进度 | `/api/analyses/:id/ws` | 已定义 |
| 获取报告 | `/api/reports/:task_id` GET | 已定义 |
| 下载 Markdown | `/api/reports/:task_id/markdown` GET | 已定义 |
| 获取 HTML | `/api/reports/:task_id/html` GET | 已定义 |

所有前端功能均有后端 API 支撑，无阻塞项。

---

## 十二、前端特有技术决策

### 12.1 不使用 React Query / SWR

理由：减少依赖数量。ReqRadar 前端数据流简单（主要是 CRUD + 一个 WebSocket），自定义 useEffect + Axios 足够覆盖需求。

### 12.2 不使用状态管理库（Redux / Zustand）

理由：应用规模不大，React Context + useReducer 足够。只有 Auth 需要全局状态，其余均为页面级局部状态。

### 12.3 不使用 CSS Modules / Tailwind

理由：Ant Design 的 `style` 属性 + 少量全局 CSS 足够。暗色主题通过 Ant Design ConfigProvider 的 algorithm 切换，无需自定义 CSS 变量维护。

### 12.4 react-markdown 而非自研 Markdown 渲染

理由：报告渲染是核心功能，react-markdown 插件生态丰富（表格、代码高亮、锚点），自研成本高风险大。

---

## 十三、Phase 2 前端扩展（暂不实现）

- 索引构建进度可视化（需后端推送索引进度事件）
- 项目记忆 CRUD（编辑术语、模块）
- 报告历史对比（diff 视图）
- PDF 导出（前端生成或后端提供）
- 代码浏览器（影响模块路径点击后展示代码）
- 移动端深度适配（当前仅基础响应式）
- 暗色主题持久化（当前仅 session 级）

---

*Plan last updated: 2026-04-22*
