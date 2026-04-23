# ReqRadar Web 前端

基于 React 19 + TypeScript + Ant Design 5 + Vite 构建的 Web 界面。

## 开发

```bash
cd frontend
npm install
npm run dev          # 开发服务器 (http://localhost:5173)
npm run build        # 生产构建 → 输出到 ../src/reqradar/web/static/
```

开发时 API 和 WebSocket 请求通过 Vite 代理转发到 `http://localhost:8000`。

## 项目结构

```
frontend/src/
├── api/          # Axios 请求封装（JWT 拦截器）
├── components/   # 通用组件（NavMenu, StepProgress, RiskBadge, FileUploader）
├── context/      # React Context（认证状态）
├── layouts/      # 布局（侧边栏 + 头部）
├── pages/        # 页面组件（懒加载）
├── types/        # TypeScript 类型定义
└── App.tsx       # 路由配置
```

## 注意事项

- 页面组件使用 `React.lazy` 按需加载
- 构建 base path 为 `/app/`，路由 basename 为 `/app`
- 401 自动跳转到 `/app/login`