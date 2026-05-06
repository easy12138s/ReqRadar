# ReqRadar Web 模块 Phase 1 重构设计文档

> 日期: 2026-05-06 | 版本: v0.7.0-web-ux

---

## 一、目标

深度优化 Web 前端模块：补齐功能缺口、重构页面布局、建立深色科技风品牌视觉体系。

## 二、改动范围

### Phase 1 范围

| 类别 | 内容 |
|------|------|
| 致命缺陷修复 | Error Boundary / WebSocket 自动重连 / Auth 加载白屏 / 死代码清理 |
| 功能补齐 | Dashboard 首页（知识向）/ 项目删除 / i18n 基础架构 |
| 布局重构 | AppLayout → AppShell（水平 TopBar + 单层 Main）/ 消除 Layout 嵌套 |
| 品牌视觉 | 深色科技风主题 / 青紫渐变主色 / 毛玻璃效果 / Skeleton 加载 |

### Phase 2+ 留待后续

项目卡片搜索分页、PDF 导出、Monaco 编辑器、浏览器通知、移动端 Drawer、全量 i18n 翻译、分析批量删除

## 三、新 Layout 架构

```
AppShell
 ├── TopBar (backdrop-blur, position:sticky)
 │    ├── Logo + 品牌名 "ReqRadar"
 │    ├── NavItems [Dashboard | 项目 | 分析 | 设置]
 │    │    路由前缀匹配高亮 (/projects/* 匹配 项目)
 │    └── UserMenu (Avatar + Dropdown: 偏好/登出)
 ├── Main (padding:24, max-width:1280, 居中)
 │    ├── ErrorBoundary (fallback UI)
 │    └── <Outlet />
 └── 废弃: 旧 AppLayout, NavMenu, SettingsLayout 嵌套
```

与旧架构核心区别：
- 去掉 Sider 垂直菜单 → 水平 TopBar，释放水平空间
- 去掉 SettingsLayout 内的第二个 Layout 嵌套
- logout 改用 `useNavigate('/login')` 替代 `window.location.href`
- 导航高亮改前缀匹配 `location.pathname.startsWith`
- Dashboard 从无到有（从 `/ → /projects` 改为 `/ → Dashboard`）

## 四、品牌主题 Token

```typescript
// Ant Design ConfigProvider theme
const theme = {
  algorithm: theme.darkAlgorithm,  // Ant Design 暗色模式
  token: {
    colorPrimary: '#00d4ff',         // 青色主色
    colorBgBase: '#0a0e17',         // 最深底色
    colorBgContainer: '#0f1624',    // 容器/卡片底色
    colorBorder: '#1e293b',          // 边框
    borderRadius: 8,                 // 统一圆角
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  components: {
    Layout: { headerBg: 'rgba(15,22,36,0.85)', bodyBg: '#0a0e17' },
    Card: { colorBgContainer: 'rgba(15,22,36,0.7)', borderRadiusLG: 12 },
    Menu: { darkItemBg: 'transparent', darkItemSelectedBg: 'rgba(0,212,255,0.1)' },
    Table: { colorBgContainer: '#0f1624', borderColor: '#1e293b' },
    Input: { colorBgContainer: '#1c2535', activeBorderColor: '#00d4ff' },
    Select: { colorBgContainer: '#1c2535', optionSelectedBg: 'rgba(0,212,255,0.12)' },
    Tag: { defaultBg: 'rgba(0,212,255,0.08)', defaultColor: '#00d4ff' },
  },
};
```

毛玻璃效果通过 CSS `backdrop-filter: blur(12px)` 单独应用于 TopBar 和 Card，不在 token 中配置。

## 五、Dashboard 页面设计（知识向）

### 布局

```
┌────────────────────────────────────────────┐
│ 欢迎回来，{displayName}                       │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│ │ 项目  │ │ 术语  │ │ 模块  │ │待确认 │       │
│ │  3   │ │  47  │ │  12  │ │  2   │       │
│ └──────┘ └──────┘ └──────┘ └──────┘       │
├────────────────────┬───────────────────────┤
│ 📚 最近记忆更新     │ 📈 术语增长趋势        │
│ ┌────────────────┐ │ ┌───────────────────┐ │
│ │ • 项目A: 新增3个│ │ │ [简易柱状图/点数图] │ │
│ │   术语 (2h ago)│ │ │                    │ │
│ │ • 项目B: 新增模块│ │ │                    │ │
│ │  (5h ago)     │ │ │                    │ │
│ │ • ...          │ │ │                    │ │
│ └────────────────┘ │ └───────────────────┘ │
├────────────────────┴───────────────────────┤
│ ⚡ 快捷操作                                 │
│ [新建项目] [提交分析] [管理模板] [配置LLM]    │
└────────────────────────────────────────────┘
```

### 数据来源

| 数据 | API | 说明 |
|------|-----|------|
| 项目数 | `GET /projects` | `projects.length` |
| 术语数 | `GET /projects/{id}/memory` | 各项目术语 sum |
| 模块数 | `GET /projects/{id}/memory` | 各项目模块 sum |
| 待确认变更 | `GET /projects/{id}/profile` | `pending_changes.length` |
| 最近更新 | `GET /projects/{id}/memory` | 取每个项目最近 changelog |
| 快捷操作 | 纯路由跳转 | 无额外 API |

### 缺失状态
- 无项目时：显示 "创建第一个项目" CTA
- 加载中：Skeleton 卡片
- API 失败：静默降级（卡片显示 `--`）

## 六、基础设施改动

### 6.1 ErrorBoundary

```tsx
// components/ErrorBoundary.tsx
// 包裹 <Outlet />，捕获子组件异常
// Fallback: Result 组件 + "刷新页面"按钮
// 生产环境隐藏错误堆栈，显示简洁文案
```

### 6.2 WebSocket 自动重连

```typescript
// hooks/useWebSocket.ts (新建)
// 特性:
// 1. 指数退避重连 (1s → 2s → 4s → 8s → max 30s)
// 2. 最大重连次数 10，超限后停止+通知用户
// 3. readyState 暴露: connecting / open / closed / reconnecting
// 4. 心跳检测 (30s ping, 10s 超时)
// 5. cleanup 时自动关闭
```

### 6.3 Auth 加载修复

```tsx
// ProtectedRoute: isLoading → <PageLoader /> (不再 return null)
// PublicRoute: isLoading → <PageLoader /> (不再 return null)
```

### 6.4 Skeleton 组件

```tsx
// components/SkeletonCard.tsx — 卡片骨架
// components/SkeletonTable.tsx — 表格骨架（3行）
// components/SkeletonStat.tsx — 统计卡片骨架
// 替换全局 Spin 为对应场景的 Skeleton
```

### 6.5 清理死代码

- 删除 `App.css` (183 行无用 Vite 脚手架残留)
- 删除 `NavMenu.tsx` (被 TopBar 替换)
- 删除 `SettingsLayout.tsx` (消除嵌套 Layout)
- 删除 `AppLayout.tsx` (被 AppShell 替换)

### 6.6 i18n 基础架构

```
i18n/
 ├── index.ts         # init + useTranslation hook
 ├── locales/
 │    ├── zh-CN.ts    # 中文 (默认)
 │    └── en-US.ts    # 英文 (Phase 2 完整翻译)
```

Phase 1 只创建架构 + 中文默认 + 英文骨架。不做全量翻译。

## 七、各页面适配

### 7.1 Login — 小幅优化

- 添加密码可见性切换
- 分离登录/注册的 loading 状态
- 错误信息展示后端返回细节

### 7.2 Projects — 功能补齐

- 新增删除按钮（Popconfirm + API 调用）
- 新增项目名称搜索（Input.Search 客户端过滤）
- 卡片悬停微动效

### 7.3 ProjectDetail — 小幅优化

- 新增删除按钮
- 从详情页直接提交分析（CTA 按钮）
- 文件树加载状态

### 7.4 ProjectProfile — 补齐字段

- 展示/编辑 `architecture_style`, `tech_stack`, `modules`
- 保留原有 description 编辑 + pending changes 审核

### 7.5 AnalysisSubmit — Tab 状态保持

- 切换 Tab 保留 form 状态
- 文件上传 Tab 也支持 depth/template/focus 参数

### 7.6 AnalysisProgress — WebSocket 重连

- 使用新的 `useWebSocket` hook
- 实时显示连接状态指示器

### 7.7 ReportView — TOC 修复

- TOC 锚点改用 `scrollIntoView` 替代 `href="#..."`

### 7.8 LLMConfig — 小幅优化

- 添加"测试连接"按钮

### 7.9 TemplateManager / SynonymManager / UserPreferences
- 视觉适配深色主题，逻辑不变

## 八、不改的文件

这些文件技术债务留到 Phase 2：
- `ChatPanel.tsx` — 消息样式区分、加载动画
- `AnalysisList.tsx` — 排序、分页优化
- `FileUploader.tsx` — 上传进度条
- `PendingChangeCard.tsx` — "展开更多"
- API 客户端类型修正
- 全量 i18n 翻译

## 九、改动文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `components/AppShell.tsx` | 新建 | 新 Layout |
| `components/ErrorBoundary.tsx` | 新建 | 全局异常捕获 |
| `components/SkeletonCard.tsx` | 新建 | 卡片骨架 |
| `components/SkeletonTable.tsx` | 新建 | 表格骨架 |
| `components/SkeletonStat.tsx` | 新建 | 统计卡片骨架 |
| `hooks/useWebSocket.ts` | 新建 | WebSocket 重连 hook |
| `i18n/index.ts` | 新建 | i18n 初始化 |
| `i18n/locales/zh-CN.ts` | 新建 | 中文翻译 |
| `i18n/locales/en-US.ts` | 新建 | 英文骨架 |
| `pages/Dashboard.tsx` | 新建 | Dashboard 首页 |
| `App.tsx` | 修改 | 新 AppShell + ErrorBoundary + 主题 + 路由 |
| `App.css` | 删除 | 死代码 |
| `main.tsx` | 修改 | 引入 i18n |
| `index.css` | 修改 | 深色背景 + 毛玻璃工具类 |
| `contexts/AuthContext.tsx` | 修改 | logout 改 SPA 导航 + loading 修复 |
| `pages/Login.tsx` | 修改 | 小幅优化 |
| `pages/Projects.tsx` | 修改 | 删除 + 搜索 |
| `pages/ProjectDetail.tsx` | 修改 | 删除 + CTA |
| `pages/ProjectProfile.tsx` | 修改 | 补齐字段 |
| `pages/AnalysisSubmit.tsx` | 修改 | Tab 状态保持 |
| `pages/AnalysisProgress.tsx` | 修改 | useWebSocket |
| `pages/ReportView.tsx` | 修改 | TOC 修复 |
| `pages/LLMConfig.tsx` | 修改 | 测试连接 |
| `AppLayout.tsx` | 删除 | 被 AppShell 替换 |
| `NavMenu.tsx` | 删除 | 导航移入 TopBar |
| `SettingsLayout.tsx` | 删除 | 消除嵌套 Layout |

**总计**: 新建 10 文件 / 修改 10 文件 / 删除 4 文件

## 十、风险

| 风险 | 缓解 |
|------|------|
| Ant Design darkAlgorithm 与自定义 token 冲突 | 先用 darkAlgorithm，再用 components 覆盖 |
| 全页重接路由可能引入导航 bug | 保留原路由路径不变，只改 Layout 渲染 |
| WebSocket hook 异步竞态 | useEffect cleanup 取消重连计时器 |
| i18n 文本散落各处难以维护 | Phase 1 仅创建架构，不强制全量翻译 |
