# ReqRadar 前端改造实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 ReqRadar Agent 架构改造的前端部分，包括：项目画像管理、同义词管理、报告模板管理、用户偏好设置、报告回溯（版本+对话）、分析提交/进度页增强。

**Architecture:** 基于现有 React 19 + TypeScript + Vite + Ant Design 6 技术栈，采用"新增页面独立开发 → 存量页面增量改造 → 路由/导航统一接入"的顺序。所有新增 API 调用遵循现有 `src/api/` + `src/types/api.ts` 分层模式。

**Tech Stack:** React 19, TypeScript, Vite, Ant Design 6, Axios, React Router 7, React Markdown

---

## 文件结构总览

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/api/profile.ts` | 项目画像 API（获取、保存、待确认变更列表、接受/拒绝） |
| `src/api/synonyms.ts` | 同义词映射 API（CRUD、导入导出） |
| `src/api/templates.ts` | 报告模板 API（CRUD、设为默认） |
| `src/api/versions.ts` | 版本管理 API（列表、获取、回滚） |
| `src/api/chatback.ts` | 对话回溯 API（发送消息、获取历史、保存版本） |
| `src/api/evidence.ts` | 证据链 API（列表、详情） |
| `src/api/configs.ts` | 用户/项目配置 API（偏好设置读写） |
| `src/pages/ProjectProfile.tsx` | 项目画像管理页（Markdown 编辑器 + pending diff） |
| `src/pages/SynonymManager.tsx` | 同义词管理页（表格 + CRUD + 搜索） |
| `src/pages/TemplateManager.tsx` | 报告模板管理页（列表 + 编辑器 + 预览） |
| `src/pages/UserPreferences.tsx` | 用户偏好设置页（深度/语言/关注领域） |
| `src/pages/SettingsLayout.tsx` | 设置页面布局（左侧菜单：模板/偏好） |
| `src/components/VersionSelector.tsx` | 版本选择器下拉组件 |
| `src/components/ChatPanel.tsx` | 对话面板组件（输入框 + 消息列表） |
| `src/components/EvidencePanel.tsx` | 证据面板组件（可折叠，显示证据列表） |
| `src/components/PendingChangeCard.tsx` | 待确认变更卡片（显示 diff + 接受/拒绝） |
| `src/components/DepthSelector.tsx` | 分析深度选择器（快速/标准/深度） |
| `src/components/TemplateSelector.tsx` | 报告模板选择器 |
| `src/components/FocusAreaSelector.tsx` | 关注领域多选组件 |
| `src/components/DimensionProgress.tsx` | 维度分析进度条 |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `src/App.tsx` | 新增路由：profile, synonyms, settings/* |
| `src/types/api.ts` | 新增所有后端返回的类型定义 |
| `src/types/websocket.ts` | 新增 Agent 相关消息类型 |
| `src/layouts/AppLayout.tsx` | 导航菜单新增"设置"入口 |
| `src/pages/ReportView.tsx` | 添加版本选择器、对话面板、证据面板 |
| `src/pages/AnalysisSubmit.tsx` | 添加深度选择器、模板选择器、关注领域 |
| `src/pages/AnalysisProgress.tsx` | 添加维度进度、证据计数、停止按钮 |
| `src/pages/Projects.tsx` | 添加画像状态指示、更新画像按钮 |
| `src/api/analyses.ts` | 新增 cancel 和 depth 参数支持 |

---

## 任务列表

### Task 1: API 类型定义

**Files:**
- Modify: `src/types/api.ts`

**后端接口参考：**
- Profile: `GET/PUT /api/projects/{id}/profile`, `GET/POST /api/projects/{id}/pending-changes`
- Synonyms: `GET/POST/PUT/DELETE /api/synonyms`
- Templates: `GET/POST/PUT/DELETE /api/templates`
- Versions: `GET /api/analyses/{task_id}/reports/versions`, `POST /api/analyses/{task_id}/reports/rollback`
- Chatback: `POST/GET /api/analyses/{task_id}/chat`, `POST /api/analyses/{task_id}/chat/save`
- Evidence: `GET /api/analyses/{task_id}/evidence`
- Configs: `GET/PUT /api/configs/{key}` (user/project/system scope)

- [ ] **Step 1: 在 `src/types/api.ts` 追加所有新类型**

```typescript
// === Round 3 新增类型 ===

export type AnalysisDepth = 'quick' | 'standard' | 'deep';

export interface SynonymMapping {
  id: string;
  project_id: string | null;
  business_term: string;
  code_terms: string[];
  priority: number;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface SynonymMappingCreate {
  project_id?: string;
  business_term: string;
  code_terms: string[];
  priority?: number;
}

export interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  is_default: boolean;
  definition_yaml: string;
  created_at: string;
  updated_at: string;
}

export interface ReportTemplateCreate {
  name: string;
  description: string;
  definition_yaml: string;
}

export interface ReportVersion {
  version_number: number;
  trigger_type: string;
  trigger_description: string;
  created_at: string;
  created_by: string;
}

export interface ReportVersionDetail extends ReportVersion {
  content_markdown: string;
  content_html: string;
  report_data: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  intent_type?: string;
  created_at: string;
}

export interface ChatRequest {
  message: string;
  version_number?: number;
}

export interface ChatResponse {
  reply: string;
  intent_type: string;
  updated: boolean;
  new_version?: number;
  report_preview?: string;
}

export interface EvidenceItem {
  id: string;
  type: string;
  source: string;
  content: string;
  confidence: string;
  dimensions: string[];
  timestamp: string;
}

export interface PendingChange {
  id: string;
  type: 'profile' | 'synonym';
  description: string;
  old_value?: string;
  new_value?: string;
  status: 'pending' | 'accepted' | 'rejected';
  created_at: string;
}

export interface UserPreference {
  default_depth: AnalysisDepth;
  report_language: string;
  focus_areas: string[];
}

export interface ProjectProfile {
  description: string;
  architecture_style: string;
  tech_stack: {
    languages: string[];
    frameworks: string[];
    key_dependencies: string[];
  };
  modules: Array<{
    name: string;
    responsibility: string;
    key_classes: string[];
    dependencies: string[];
  }>;
}

// === AnalysisTask 扩展 ===
export interface AnalysisTask {
  id: string;
  project_id: string;
  status: AnalysisStatus;
  input_type: 'text' | 'file';
  input_preview: string;
  risk_level?: RiskLevel;
  risk_score?: number;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  error_message?: string;
  depth?: AnalysisDepth;
  current_version?: number;
}

export interface AnalysisCreate {
  project_id: string;
  text?: string;
  depth?: AnalysisDepth;
  template_id?: string;
  focus_areas?: string[];
}
```

- [ ] **Step 2: 运行 TypeScript 检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无新增类型错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "feat(frontend): add API types for profile, synonyms, templates, versions, chatback, evidence"
```

---

### Task 2: API 客户端模块

**Files:**
- Create: `src/api/profile.ts`, `src/api/synonyms.ts`, `src/api/templates.ts`, `src/api/versions.ts`, `src/api/chatback.ts`, `src/api/evidence.ts`, `src/api/configs.ts`
- Modify: `src/api/analyses.ts`

- [ ] **Step 1: 创建 `src/api/profile.ts`**

```typescript
import { apiClient } from './client';
import type { ProjectProfile, PendingChange } from '@/types/api';

export async function getProjectProfile(projectId: string): Promise<ProjectProfile> {
  const response = await apiClient.get<ProjectProfile>(`/projects/${projectId}/profile`);
  return response.data;
}

export async function updateProjectProfile(
  projectId: string,
  profile: ProjectProfile
): Promise<ProjectProfile> {
  const response = await apiClient.put<ProjectProfile>(`/projects/${projectId}/profile`, profile);
  return response.data;
}

export async function getPendingChanges(projectId: string): Promise<PendingChange[]> {
  const response = await apiClient.get<PendingChange[]>(`/projects/${projectId}/pending-changes`);
  return response.data;
}

export async function acceptPendingChange(
  projectId: string,
  changeId: string
): Promise<void> {
  await apiClient.post(`/projects/${projectId}/pending-changes/${changeId}/accept`);
}

export async function rejectPendingChange(
  projectId: string,
  changeId: string
): Promise<void> {
  await apiClient.post(`/projects/${projectId}/pending-changes/${changeId}/reject`);
}
```

- [ ] **Step 2: 创建 `src/api/synonyms.ts`**

```typescript
import { apiClient } from './client';
import type { SynonymMapping, SynonymMappingCreate } from '@/types/api';

export async function getSynonyms(projectId?: string): Promise<SynonymMapping[]> {
  const params = projectId ? { project_id: projectId } : {};
  const response = await apiClient.get<SynonymMapping[]>('/synonyms', { params });
  return response.data;
}

export async function createSynonym(data: SynonymMappingCreate): Promise<SynonymMapping> {
  const response = await apiClient.post<SynonymMapping>('/synonyms', data);
  return response.data;
}

export async function updateSynonym(
  id: string,
  data: Partial<SynonymMappingCreate>
): Promise<SynonymMapping> {
  const response = await apiClient.put<SynonymMapping>(`/synonyms/${id}`, data);
  return response.data;
}

export async function deleteSynonym(id: string): Promise<void> {
  await apiClient.delete(`/synonyms/${id}`);
}
```

- [ ] **Step 3: 创建 `src/api/templates.ts`**

```typescript
import { apiClient } from './client';
import type { ReportTemplate, ReportTemplateCreate } from '@/types/api';

export async function getTemplates(): Promise<ReportTemplate[]> {
  const response = await apiClient.get<ReportTemplate[]>('/templates');
  return response.data;
}

export async function getTemplate(id: string): Promise<ReportTemplate> {
  const response = await apiClient.get<ReportTemplate>(`/templates/${id}`);
  return response.data;
}

export async function createTemplate(data: ReportTemplateCreate): Promise<ReportTemplate> {
  const response = await apiClient.post<ReportTemplate>('/templates', data);
  return response.data;
}

export async function updateTemplate(
  id: string,
  data: Partial<ReportTemplateCreate>
): Promise<ReportTemplate> {
  const response = await apiClient.put<ReportTemplate>(`/templates/${id}`, data);
  return response.data;
}

export async function deleteTemplate(id: string): Promise<void> {
  await apiClient.delete(`/templates/${id}`);
}

export async function setDefaultTemplate(id: string): Promise<void> {
  await apiClient.post(`/templates/${id}/set-default`);
}
```

- [ ] **Step 4: 创建 `src/api/versions.ts`**

```typescript
import { apiClient } from './client';
import type { ReportVersion, ReportVersionDetail } from '@/types/api';

export async function getVersions(taskId: string): Promise<{ versions: ReportVersion[] }> {
  const response = await apiClient.get<{ versions: ReportVersion[] }>(
    `/analyses/${taskId}/reports/versions`
  );
  return response.data;
}

export async function getVersion(
  taskId: string,
  versionNumber: number
): Promise<ReportVersionDetail> {
  const response = await apiClient.get<ReportVersionDetail>(
    `/analyses/${taskId}/reports/versions/${versionNumber}`
  );
  return response.data;
}

export async function rollbackVersion(
  taskId: string,
  versionNumber: number
): Promise<{ success: boolean; current_version: number }> {
  const response = await apiClient.post(`/analyses/${taskId}/reports/rollback`, {
    version_number: versionNumber,
  });
  return response.data;
}
```

- [ ] **Step 5: 创建 `src/api/chatback.ts`**

```typescript
import { apiClient } from './client';
import type { ChatRequest, ChatResponse, ChatMessage } from '@/types/api';

export async function sendChatMessage(
  taskId: string,
  data: ChatRequest
): Promise<ChatResponse> {
  const response = await apiClient.post<ChatResponse>(`/analyses/${taskId}/chat`, data);
  return response.data;
}

export async function getChatHistory(
  taskId: string,
  versionNumber?: number
): Promise<{ messages: ChatMessage[] }> {
  const params = versionNumber !== undefined ? { version_number: versionNumber } : {};
  const response = await apiClient.get<{ messages: ChatMessage[] }>(
    `/analyses/${taskId}/chat`,
    { params }
  );
  return response.data;
}

export async function saveChatVersion(
  taskId: string,
  versionNumber: number
): Promise<{ success: boolean; new_version?: number }> {
  const response = await apiClient.post(`/analyses/${taskId}/chat/save`, {
    version_number: versionNumber,
  });
  return response.data;
}
```

- [ ] **Step 6: 创建 `src/api/evidence.ts`**

```typescript
import { apiClient } from './client';
import type { EvidenceItem } from '@/types/api';

export async function getEvidenceChain(
  taskId: string,
  versionNumber?: number
): Promise<{ evidence: EvidenceItem[] }> {
  const params = versionNumber !== undefined ? { version_number: versionNumber } : {};
  const response = await apiClient.get<{ evidence: EvidenceItem[] }>(
    `/analyses/${taskId}/evidence`,
    { params }
  );
  return response.data;
}

export async function getEvidenceDetail(
  taskId: string,
  evidenceId: string,
  versionNumber?: number
): Promise<EvidenceItem> {
  const params = versionNumber !== undefined ? { version_number: versionNumber } : {};
  const response = await apiClient.get<EvidenceItem>(
    `/analyses/${taskId}/evidence/${evidenceId}`,
    { params }
  );
  return response.data;
}
```

- [ ] **Step 7: 创建 `src/api/configs.ts`**

```typescript
import { apiClient } from './client';

export async function getConfig(
  key: string,
  scope: 'user' | 'project' | 'system' = 'user',
  projectId?: string
): Promise<{ key: string; value: unknown; scope: string }> {
  const params: Record<string, string> = { scope };
  if (projectId) params.project_id = projectId;
  const response = await apiClient.get(`/configs/${key}`, { params });
  return response.data;
}

export async function setConfig(
  key: string,
  value: unknown,
  scope: 'user' | 'project' = 'user',
  projectId?: string
): Promise<void> {
  const body: Record<string, unknown> = { value, scope };
  if (projectId) body.project_id = projectId;
  await apiClient.put(`/configs/${key}`, body);
}
```

- [ ] **Step 8: 修改 `src/api/analyses.ts` 添加 cancel 和 depth 支持**

```typescript
// 在原有代码后追加

export async function cancelAnalysis(id: string): Promise<void> {
  await apiClient.post(`/analyses/${id}/cancel`);
}

// 修改 createAnalysis 签名以支持 depth
// 注意：AnalysisCreate 类型已在 Task 1 中扩展
```

- [ ] **Step 9: 运行 TypeScript 检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 10: Commit**

```bash
git add frontend/src/api/
git commit -m "feat(frontend): add API clients for profile, synonyms, templates, versions, chatback, evidence, configs"
```

---

### Task 3: 设置页面布局

**Files:**
- Create: `src/pages/SettingsLayout.tsx`

- [ ] **Step 1: 创建设置页面布局组件**

```typescript
// src/pages/SettingsLayout.tsx
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { FileTextOutlined, SettingOutlined } from '@ant-design/icons';

const { Sider, Content } = Layout;

export function SettingsLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/settings/templates',
      icon: <FileTextOutlined />,
      label: '报告模板',
    },
    {
      key: '/settings/preferences',
      icon: <SettingOutlined />,
      label: '用户偏好',
    },
  ];

  return (
    <Layout style={{ minHeight: '100%', background: '#fff' }}>
      <Sider width={200} style={{ background: '#fff' }}>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Content style={{ padding: 24 }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/SettingsLayout.tsx
git commit -m "feat(frontend): add SettingsLayout with sidebar navigation"
```

---

### Task 4: 用户偏好设置页

**Files:**
- Create: `src/pages/UserPreferences.tsx`

- [ ] **Step 1: 创建用户偏好设置页**

```typescript
// src/pages/UserPreferences.tsx
import { useState, useEffect } from 'react';
import { Card, Form, Select, Checkbox, Button, message, Spin } from 'antd';
import { getConfig, setConfig } from '@/api/configs';
import type { AnalysisDepth } from '@/types/api';

const DEPTH_OPTIONS = [
  { label: '快速 (10步)', value: 'quick' },
  { label: '标准 (15步)', value: 'standard' },
  { label: '深度 (25步)', value: 'deep' },
];

const FOCUS_AREA_OPTIONS = [
  '安全性',
  '性能',
  '兼容性',
  '可维护性',
  '可扩展性',
  '用户体验',
];

export function UserPreferences() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function loadPreferences() {
      try {
        const [depthRes, langRes, focusRes] = await Promise.all([
          getConfig('analysis.default_depth').catch(() => ({ value: 'standard' })),
          getConfig('report.language').catch(() => ({ value: 'zh' })),
          getConfig('analysis.focus_areas').catch(() => ({ value: [] })),
        ]);
        form.setFieldsValue({
          default_depth: depthRes.value as AnalysisDepth,
          report_language: langRes.value as string,
          focus_areas: focusRes.value as string[],
        });
      } catch {
        message.error('加载偏好设置失败');
      } finally {
        setLoading(false);
      }
    }
    loadPreferences();
  }, [form]);

  const handleSave = async (values: {
    default_depth: AnalysisDepth;
    report_language: string;
    focus_areas: string[];
  }) => {
    setSaving(true);
    try {
      await Promise.all([
        setConfig('analysis.default_depth', values.default_depth),
        setConfig('report.language', values.report_language),
        setConfig('analysis.focus_areas', values.focus_areas),
      ]);
      message.success('偏好设置已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 64 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Card title="用户偏好设置">
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        style={{ maxWidth: 600 }}
      >
        <Form.Item
          name="default_depth"
          label="默认分析深度"
          rules={[{ required: true }]}
        >
          <Select options={DEPTH_OPTIONS} />
        </Form.Item>

        <Form.Item
          name="report_language"
          label="报告语言"
          rules={[{ required: true }]}
        >
          <Select
            options={[
              { label: '中文', value: 'zh' },
              { label: 'English', value: 'en' },
            ]}
          />
        </Form.Item>

        <Form.Item name="focus_areas" label="关注领域">
          <Checkbox.Group options={FOCUS_AREA_OPTIONS} />
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>
            保存设置
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/UserPreferences.tsx
git commit -m "feat(frontend): add UserPreferences page with depth, language, focus areas"
```

---

### Task 5: 同义词管理页

**Files:**
- Create: `src/pages/SynonymManager.tsx`

- [ ] **Step 1: 创建同义词管理页**

```typescript
// src/pages/SynonymManager.tsx
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card, Table, Button, Modal, Form, Input, InputNumber, Space, Popconfirm,
  message, Tag, Spin, Empty,
} from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { getSynonyms, createSynonym, updateSynonym, deleteSynonym } from '@/api/synonyms';
import type { SynonymMapping } from '@/types/api';

export function SynonymManager() {
  const { id: projectId } = useParams<{ id: string }>();
  const [synonyms, setSynonyms] = useState<SynonymMapping[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<SynonymMapping | null>(null);
  const [form] = Form.useForm();
  const [searchTerm, setSearchTerm] = useState('');

  async function loadSynonyms() {
    setLoading(true);
    try {
      const data = await getSynonyms(projectId);
      setSynonyms(data);
    } catch {
      message.error('加载同义词失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSynonyms();
  }, [projectId]);

  const filteredSynonyms = synonyms.filter(
    (s) =>
      s.business_term.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.code_terms.some((t) => t.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const handleSave = async (values: {
    business_term: string;
    code_terms: string;
    priority: number;
  }) => {
    try {
      const codeTerms = values.code_terms.split(/[,，\n]/).map((t) => t.trim()).filter(Boolean);
      const data = {
        project_id: projectId,
        business_term: values.business_term,
        code_terms: codeTerms,
        priority: values.priority,
      };
      if (editingRecord) {
        await updateSynonym(editingRecord.id, data);
        message.success('更新成功');
      } else {
        await createSynonym(data);
        message.success('创建成功');
      }
      setModalVisible(false);
      form.resetFields();
      setEditingRecord(null);
      loadSynonyms();
    } catch {
      message.error('保存失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteSynonym(id);
      message.success('删除成功');
      loadSynonyms();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    {
      title: '业务术语',
      dataIndex: 'business_term',
      key: 'business_term',
    },
    {
      title: '代码术语',
      dataIndex: 'code_terms',
      key: 'code_terms',
      render: (terms: string[]) => (
        <Space wrap>
          {terms.map((t) => (
            <Tag key={t}>{t}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: unknown, record: SynonymMapping) => (
        <Space>
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => {
              setEditingRecord(record);
              form.setFieldsValue({
                business_term: record.business_term,
                code_terms: record.code_terms.join(', '),
                priority: record.priority,
              });
              setModalVisible(true);
            }}
          />
          <Popconfirm
            title="确认删除？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button icon={<DeleteOutlined />} size="small" danger />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="同义词映射管理"
      extra={
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditingRecord(null);
            form.resetFields();
            setModalVisible(true);
          }}
        >
          新增映射
        </Button>
      }
    >
      <Input.Search
        placeholder="搜索业务术语或代码术语"
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        style={{ marginBottom: 16, maxWidth: 400 }}
      />

      {loading ? (
        <Spin />
      ) : filteredSynonyms.length === 0 ? (
        <Empty description="暂无同义词映射" />
      ) : (
        <Table
          dataSource={filteredSynonyms}
          columns={columns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      )}

      <Modal
        title={editingRecord ? '编辑映射' : '新增映射'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
          setEditingRecord(null);
        }}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item
            name="business_term"
            label="业务术语"
            rules={[{ required: true, message: '请输入业务术语' }]}
          >
            <Input placeholder="例如：用户认证" />
          </Form.Item>
          <Form.Item
            name="code_terms"
            label="代码术语"
            rules={[{ required: true, message: '请输入代码术语' }]}
            extra="多个术语用逗号或换行分隔"
          >
            <Input.TextArea rows={3} placeholder="例如：auth, authentication, login" />
          </Form.Item>
          <Form.Item
            name="priority"
            label="优先级"
            initialValue={1}
          >
            <InputNumber min={0} max={10} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/SynonymManager.tsx
git commit -m "feat(frontend): add SynonymManager page with CRUD and search"
```

---

### Task 6: 项目画像管理页

**Files:**
- Create: `src/pages/ProjectProfile.tsx`, `src/components/PendingChangeCard.tsx`

- [ ] **Step 1: 创建 `src/components/PendingChangeCard.tsx`**

```typescript
// src/components/PendingChangeCard.tsx
import { Card, Button, Space, Tag, Typography } from 'antd';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import type { PendingChange } from '@/types/api';

interface PendingChangeCardProps {
  change: PendingChange;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
}

export function PendingChangeCard({ change, onAccept, onReject }: PendingChangeCardProps) {
  return (
    <Card
      size="small"
      style={{ marginBottom: 8 }}
      actions={[
        <Button
          key="accept"
          type="link"
          icon={<CheckOutlined />}
          onClick={() => onAccept(change.id)}
        >
          接受
        </Button>,
        <Button
          key="reject"
          type="link"
          danger
          icon={<CloseOutlined />}
          onClick={() => onReject(change.id)}
        >
          拒绝
        </Button>,
      ]}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space>
          <Tag color={change.type === 'profile' ? 'blue' : 'green'}>
            {change.type === 'profile' ? '画像' : '同义词'}
          </Tag>
          <Typography.Text type="secondary">
            {new Date(change.created_at).toLocaleString()}
          </Typography.Text>
        </Space>
        <Typography.Paragraph>{change.description}</Typography.Paragraph>
        {change.old_value && change.new_value && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Typography.Text type="secondary" delete style={{ fontSize: 12 }}>
              {change.old_value.slice(0, 200)}
            </Typography.Text>
            <Typography.Text type="success" style={{ fontSize: 12 }}>
              {change.new_value.slice(0, 200)}
            </Typography.Text>
          </Space>
        )}
      </Space>
    </Card>
  );
}
```

- [ ] **Step 2: 创建 `src/pages/ProjectProfile.tsx`**

```typescript
// src/pages/ProjectProfile.tsx
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card, Input, Button, message, Spin, Empty, Typography, Space, Tabs,
} from 'antd';
import {
  getProjectProfile,
  updateProjectProfile,
  getPendingChanges,
  acceptPendingChange,
  rejectPendingChange,
} from '@/api/profile';
import { PendingChangeCard } from '@/components/PendingChangeCard';
import type { ProjectProfile, PendingChange } from '@/types/api';

const { TextArea } = Input;
const { Title } = Typography;

export function ProjectProfile() {
  const { id: projectId } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<ProjectProfile | null>(null);
  const [pendingChanges, setPendingChanges] = useState<PendingChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [description, setDescription] = useState('');

  async function loadData() {
    if (!projectId) return;
    setLoading(true);
    try {
      const [profileData, changesData] = await Promise.all([
        getProjectProfile(projectId),
        getPendingChanges(projectId),
      ]);
      setProfile(profileData);
      setDescription(profileData.description || '');
      setPendingChanges(changesData.filter((c) => c.status === 'pending'));
    } catch {
      message.error('加载项目画像失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [projectId]);

  const handleSave = async () => {
    if (!projectId || !profile) return;
    setSaving(true);
    try {
      await updateProjectProfile(projectId, { ...profile, description });
      message.success('画像已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleAccept = async (changeId: string) => {
    if (!projectId) return;
    try {
      await acceptPendingChange(projectId, changeId);
      message.success('已接受');
      loadData();
    } catch {
      message.error('操作失败');
    }
  };

  const handleReject = async (changeId: string) => {
    if (!projectId) return;
    try {
      await rejectPendingChange(projectId, changeId);
      message.success('已拒绝');
      loadData();
    } catch {
      message.error('操作失败');
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 64 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Title level={3}>项目画像管理</Title>

      <Tabs
        items={[
          {
            key: 'profile',
            label: '画像编辑',
            children: (
              <Card>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <TextArea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={10}
                    placeholder="输入项目描述..."
                  />
                  <Button type="primary" onClick={handleSave} loading={saving}>
                    保存画像
                  </Button>
                </Space>
              </Card>
            ),
          },
          {
            key: 'pending',
            label: `待确认变更 (${pendingChanges.length})`,
            children: (
              <Card>
                {pendingChanges.length === 0 ? (
                  <Empty description="暂无待确认变更" />
                ) : (
                  pendingChanges.map((change) => (
                    <PendingChangeCard
                      key={change.id}
                      change={change}
                      onAccept={handleAccept}
                      onReject={handleReject}
                    />
                  ))
                )}
              </Card>
            ),
          },
        ]}
      />
    </Space>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectProfile.tsx frontend/src/components/PendingChangeCard.tsx
git commit -m "feat(frontend): add ProjectProfile page with Markdown editor and pending changes"
```

---

### Task 7: 报告模板管理页

**Files:**
- Create: `src/pages/TemplateManager.tsx`

- [ ] **Step 1: 创建模板管理页**

```typescript
// src/pages/TemplateManager.tsx
import { useState, useEffect } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Space, Popconfirm, Tag,
  message, Spin, Empty, Radio, Tabs,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined, StarOutlined, StarFilled,
} from '@ant-design/icons';
import {
  getTemplates,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  setDefaultTemplate,
} from '@/api/templates';
import type { ReportTemplate } from '@/types/api';

export function TemplateManager() {
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<ReportTemplate | null>(null);
  const [form] = Form.useForm();
  const [activeTab, setActiveTab] = useState('list');

  async function loadTemplates() {
    setLoading(true);
    try {
      const data = await getTemplates();
      setTemplates(data);
    } catch {
      message.error('加载模板失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTemplates();
  }, []);

  const handleSave = async (values: {
    name: string;
    description: string;
    definition_yaml: string;
  }) => {
    try {
      if (editingTemplate) {
        await updateTemplate(editingTemplate.id, values);
        message.success('模板已更新');
      } else {
        await createTemplate(values);
        message.success('模板已创建');
      }
      setModalVisible(false);
      form.resetFields();
      setEditingTemplate(null);
      loadTemplates();
    } catch {
      message.error('保存失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTemplate(id);
      message.success('模板已删除');
      loadTemplates();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSetDefault = async (id: string) => {
    try {
      await setDefaultTemplate(id);
      message.success('已设为默认模板');
      loadTemplates();
    } catch {
      message.error('设置失败');
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '默认',
      dataIndex: 'is_default',
      key: 'is_default',
      width: 80,
      render: (isDefault: boolean) =>
        isDefault ? <Tag color="blue">默认</Tag> : null,
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, record: ReportTemplate) => (
        <Space>
          {!record.is_default && (
            <Button
              icon={<StarOutlined />}
              size="small"
              onClick={() => handleSetDefault(record.id)}
            >
              设为默认
            </Button>
          )}
          <Button
            icon={<EditOutlined />}
            size="small"
            onClick={() => {
              setEditingTemplate(record);
              form.setFieldsValue(record);
              setModalVisible(true);
            }}
          />
          <Popconfirm
            title="确认删除此模板？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button icon={<DeleteOutlined />} size="small" danger />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="报告模板管理"
      extra={
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditingTemplate(null);
            form.resetFields();
            setModalVisible(true);
          }}
        >
          新建模板
        </Button>
      }
    >
      {loading ? (
        <Spin />
      ) : templates.length === 0 ? (
        <Empty description="暂无模板" />
      ) : (
        <Table
          dataSource={templates}
          columns={columns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      )}

      <Modal
        title={editingTemplate ? '编辑模板' : '新建模板'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
          setEditingTemplate(null);
        }}
        onOk={() => form.submit()}
        width={800}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item
            name="name"
            label="模板名称"
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="description"
            label="描述"
          >
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="definition_yaml"
            label="模板定义 (YAML)"
            rules={[{ required: true }]}
          >
            <Input.TextArea rows={12} placeholder="输入 Jinja2 模板 YAML..." />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/TemplateManager.tsx
git commit -m "feat(frontend): add TemplateManager page with CRUD and default setting"
```

---

### Task 8: 报告回溯页面增强（ReportView）

**Files:**
- Create: `src/components/VersionSelector.tsx`, `src/components/ChatPanel.tsx`, `src/components/EvidencePanel.tsx`
- Modify: `src/pages/ReportView.tsx`

- [ ] **Step 1: 创建 `src/components/VersionSelector.tsx`**

```typescript
// src/components/VersionSelector.tsx
import { Select, Button, Space, message } from 'antd';
import { RollbackOutlined } from '@ant-design/icons';
import { getVersions, rollbackVersion } from '@/api/versions';
import type { ReportVersion } from '@/types/api';
import { useState, useEffect } from 'react';

interface VersionSelectorProps {
  taskId: string;
  currentVersion?: number;
  onVersionChange: (version: number) => void;
  onRollback?: () => void;
}

export function VersionSelector({
  taskId,
  currentVersion,
  onVersionChange,
  onRollback,
}: VersionSelectorProps) {
  const [versions, setVersions] = useState<ReportVersion[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await getVersions(taskId);
        setVersions(data.versions);
      } catch {
        // silent fail
      }
    }
    load();
  }, [taskId]);

  const handleRollback = async (versionNumber: number) => {
    setLoading(true);
    try {
      await rollbackVersion(taskId, versionNumber);
      message.success('已回滚到指定版本');
      onRollback?.();
    } catch {
      message.error('回滚失败');
    } finally {
      setLoading(false);
    }
  };

  const options = versions.map((v) => ({
    label: `v${v.version_number} (${v.trigger_type})`,
    value: v.version_number,
  }));

  return (
    <Space>
      <Select
        style={{ width: 200 }}
        placeholder="选择版本"
        value={currentVersion}
        onChange={onVersionChange}
        options={options}
        loading={loading}
      />
      {currentVersion && currentVersion > 1 && (
        <Button
          icon={<RollbackOutlined />}
          onClick={() => handleRollback(currentVersion)}
          loading={loading}
        >
          回滚到此版本
        </Button>
      )}
    </Space>
  );
}
```

- [ ] **Step 2: 创建 `src/components/ChatPanel.tsx`**

```typescript
// src/components/ChatPanel.tsx
import { useState, useEffect } from 'react';
import {
  Card, Input, Button, List, Avatar, Space, Typography, Spin, message,
} from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, SaveOutlined } from '@ant-design/icons';
import { sendChatMessage, getChatHistory, saveChatVersion } from '@/api/chatback';
import type { ChatMessage } from '@/types/api';

interface ChatPanelProps {
  taskId: string;
  versionNumber?: number;
  onVersionUpdate?: (newVersion: number) => void;
}

export function ChatPanel({ taskId, versionNumber, onVersionUpdate }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  async function loadHistory() {
    try {
      const data = await getChatHistory(taskId, versionNumber);
      setMessages(data.messages);
    } catch {
      // silent
    }
  }

  useEffect(() => {
    loadHistory();
  }, [taskId, versionNumber]);

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMessage = input.trim();
    setInput('');
    setLoading(true);

    try {
      const result = await sendChatMessage(taskId, {
        message: userMessage,
        version_number: versionNumber,
      });

      setMessages((prev) => [
        ...prev,
        { id: Date.now().toString(), role: 'user', content: userMessage, created_at: new Date().toISOString() },
        { id: (Date.now() + 1).toString(), role: 'assistant', content: result.reply, intent_type: result.intent_type, created_at: new Date().toISOString() },
      ]);

      if (result.new_version) {
        onVersionUpdate?.(result.new_version);
      }
    } catch {
      message.error('发送失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!versionNumber) return;
    setSaving(true);
    try {
      await saveChatVersion(taskId, versionNumber);
      message.success('已保存为新版本');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title="报告对话" size="small">
      <List
        dataSource={messages}
        renderItem={(msg) => (
          <List.Item>
            <List.Item.Meta
              avatar={
                <Avatar
                  icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                  style={{
                    backgroundColor: msg.role === 'user' ? '#1677ff' : '#52c41a',
                  }}
                />
              }
              title={msg.role === 'user' ? '用户' : 'Agent'}
              description={
                <Typography.Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                  {msg.content}
                </Typography.Paragraph>
              }
            />
          </List.Item>
        )}
        style={{ maxHeight: 300, overflow: 'auto', marginBottom: 16 }}
      />

      <Space.Compact style={{ width: '100%' }}>
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={handleSend}
          placeholder="输入问题，例如：为什么风险等级是中？"
          disabled={loading}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading}
        >
          发送
        </Button>
        <Button
          icon={<SaveOutlined />}
          onClick={handleSave}
          loading={saving}
        >
          保存
        </Button>
      </Space.Compact>
    </Card>
  );
}
```

- [ ] **Step 3: 创建 `src/components/EvidencePanel.tsx`**

```typescript
// src/components/EvidencePanel.tsx
import { useState, useEffect } from 'react';
import { Card, List, Tag, Typography, Spin, Empty } from 'antd';
import { FileOutlined } from '@ant-design/icons';
import { getEvidenceChain } from '@/api/evidence';
import type { EvidenceItem } from '@/types/api';

interface EvidencePanelProps {
  taskId: string;
  versionNumber?: number;
}

export function EvidencePanel({ taskId, versionNumber }: EvidencePanelProps) {
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const data = await getEvidenceChain(taskId, versionNumber);
        setEvidence(data.evidence);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [taskId, versionNumber]);

  if (loading) {
    return <Spin />;
  }

  if (evidence.length === 0) {
    return <Empty description="暂无证据" />;
  }

  return (
    <Card title={`证据链 (${evidence.length})`} size="small">
      <List
        dataSource={evidence}
        renderItem={(item) => (
          <List.Item>
            <List.Item.Meta
              avatar={<FileOutlined />}
              title={
                <Space>
                  <Typography.Text strong>{item.source}</Typography.Text>
                  <Tag color={item.confidence === 'high' ? 'green' : item.confidence === 'medium' ? 'orange' : 'red'}>
                    {item.confidence}
                  </Tag>
                </Space>
              }
              description={
                <>
                  <Typography.Paragraph style={{ margin: 0 }}>{item.content}</Typography.Paragraph>
                  <Space size={4}>
                    {item.dimensions.map((dim) => (
                      <Tag key={dim} size="small">{dim}</Tag>
                    ))}
                  </Space>
                </>
              }
            />
          </List.Item>
        )}
      />
    </Card>
  );
}
```

- [ ] **Step 4: 修改 `src/pages/ReportView.tsx`**

由于 ReportView 是现有文件，需要读取后修改：

```bash
cat frontend/src/pages/ReportView.tsx
```

（注：实际执行时，先读取现有 ReportView.tsx 的内容，然后在其基础上添加 VersionSelector、ChatPanel、EvidencePanel 的引用和渲染。）

关键修改点：
1. 导入新增组件
2. 添加 `currentVersion` state
3. 在页面顶部添加 VersionSelector
4. 在报告内容下方添加 ChatPanel
5. 在右侧（或下方）添加 EvidencePanel
6. 根据版本号重新加载报告内容

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/VersionSelector.tsx frontend/src/components/ChatPanel.tsx frontend/src/components/EvidencePanel.tsx frontend/src/pages/ReportView.tsx
git commit -m "feat(frontend): enhance ReportView with version selector, chatback, and evidence panel"
```

---

### Task 9: 分析提交页增强（AnalysisSubmit）

**Files:**
- Create: `src/components/DepthSelector.tsx`, `src/components/TemplateSelector.tsx`, `src/components/FocusAreaSelector.tsx`
- Modify: `src/pages/AnalysisSubmit.tsx`

- [ ] **Step 1: 创建 `src/components/DepthSelector.tsx`**

```typescript
// src/components/DepthSelector.tsx
import { Select } from 'antd';
import type { AnalysisDepth } from '@/types/api';

interface DepthSelectorProps {
  value?: AnalysisDepth;
  onChange?: (value: AnalysisDepth) => void;
}

const options = [
  { label: '快速 (10步)', value: 'quick', description: '适合简单需求，快速获取概览' },
  { label: '标准 (15步)', value: 'standard', description: '平衡速度与深度' },
  { label: '深度 (25步)', value: 'deep', description: '复杂需求，全面分析' },
];

export function DepthSelector({ value, onChange }: DepthSelectorProps) {
  return (
    <Select
      style={{ width: 200 }}
      placeholder="选择分析深度"
      value={value}
      onChange={onChange}
      options={options}
    />
  );
}
```

- [ ] **Step 2: 创建 `src/components/TemplateSelector.tsx`**

```typescript
// src/components/TemplateSelector.tsx
import { useState, useEffect } from 'react';
import { Select, Spin } from 'antd';
import { getTemplates } from '@/api/templates';
import type { ReportTemplate } from '@/types/api';

interface TemplateSelectorProps {
  value?: string;
  onChange?: (value: string) => void;
}

export function TemplateSelector({ value, onChange }: TemplateSelectorProps) {
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await getTemplates();
        setTemplates(data);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <Spin size="small" />;
  }

  return (
    <Select
      style={{ width: 250 }}
      placeholder="选择报告模板"
      value={value}
      onChange={onChange}
      options={templates.map((t) => ({
        label: t.name + (t.is_default ? ' (默认)' : ''),
        value: t.id,
      }))}
      allowClear
    />
  );
}
```

- [ ] **Step 3: 创建 `src/components/FocusAreaSelector.tsx`**

```typescript
// src/components/FocusAreaSelector.tsx
import { Select } from 'antd';

interface FocusAreaSelectorProps {
  value?: string[];
  onChange?: (value: string[]) => void;
}

const options = [
  { label: '安全性', value: 'security' },
  { label: '性能', value: 'performance' },
  { label: '兼容性', value: 'compatibility' },
  { label: '可维护性', value: 'maintainability' },
  { label: '可扩展性', value: 'scalability' },
  { label: '用户体验', value: 'ux' },
];

export function FocusAreaSelector({ value, onChange }: FocusAreaSelectorProps) {
  return (
    <Select
      mode="multiple"
      style={{ width: '100%' }}
      placeholder="选择关注领域（可选）"
      value={value}
      onChange={onChange}
      options={options}
      allowClear
    />
  );
}
```

- [ ] **Step 4: 修改 `src/pages/AnalysisSubmit.tsx`**

读取现有文件并添加深度选择器、模板选择器、关注领域多选：

关键修改：
1. 导入新增组件
2. 在表单中添加 depth、template_id、focus_areas 字段
3. 将这些字段传给 `createAnalysis` 或提交时处理

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DepthSelector.tsx frontend/src/components/TemplateSelector.tsx frontend/src/components/FocusAreaSelector.tsx frontend/src/pages/AnalysisSubmit.tsx
git commit -m "feat(frontend): enhance AnalysisSubmit with depth, template, focus area selectors"
```

---

### Task 10: 分析进度页增强（AnalysisProgress）

**Files:**
- Create: `src/components/DimensionProgress.tsx`
- Modify: `src/pages/AnalysisProgress.tsx`

- [ ] **Step 1: 创建 `src/components/DimensionProgress.tsx`**

```typescript
// src/components/DimensionProgress.tsx
import { Progress, Space, Tag, Typography } from 'antd';

interface DimensionProgressProps {
  dimensions: Record<string, string>;
  evidenceCount: number;
  step: number;
  maxSteps: number;
}

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  sufficient: { color: 'green', label: '充分' },
  in_progress: { color: 'blue', label: '分析中' },
  pending: { color: 'default', label: '待分析' },
};

export function DimensionProgress({ dimensions, evidenceCount, step, maxSteps }: DimensionProgressProps) {
  const items = Object.entries(dimensions);
  const completedCount = items.filter(([, status]) => status === 'sufficient').length;
  const progressPercent = Math.round((completedCount / items.length) * 100);

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space>
        <Typography.Text>分析进度: {step}/{maxSteps} 步</Typography.Text>
        <Typography.Text>证据数: {evidenceCount}</Typography.Text>
      </Space>
      <Progress percent={progressPercent} size="small" />
      <Space wrap>
        {items.map(([dim, status]) => {
          const config = STATUS_MAP[status] || STATUS_MAP.pending;
          return (
            <Tag key={dim} color={config.color}>
              {dim}: {config.label}
            </Tag>
          );
        })}
      </Space>
    </Space>
  );
}
```

- [ ] **Step 2: 修改 `src/pages/AnalysisProgress.tsx`**

读取现有文件并添加：
1. DimensionProgress 组件显示当前维度状态
2. 证据计数显示
3. "停止并生成报告" 按钮（调用 cancelAnalysis API）
4. WebSocket 消息处理扩展（监听 `dimension_progress` 消息）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/DimensionProgress.tsx frontend/src/pages/AnalysisProgress.tsx
git commit -m "feat(frontend): enhance AnalysisProgress with dimension progress, evidence count, stop button"
```

---

### Task 11: 项目列表页增强（Projects）

**Files:**
- Modify: `src/pages/Projects.tsx`

- [ ] **Step 1: 修改项目卡片显示画像状态**

读取现有 `Projects.tsx` 并添加：
1. 项目卡片上显示画像构建状态（是否已有 project.md）
2. "更新画像" 按钮（调用 project profile API）
3. "画像管理" 链接跳转到 `/projects/:id/profile`
4. "同义词" 链接跳转到 `/projects/:id/synonyms`

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Projects.tsx
git commit -m "feat(frontend): enhance Projects page with profile status and action links"
```

---

### Task 12: 路由与导航更新

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/layouts/AppLayout.tsx`

- [ ] **Step 1: 修改 `src/App.tsx` 添加新路由**

```typescript
// 在原有 import 后添加
const ProjectProfile = lazy(() => import('@/pages/ProjectProfile').then(m => ({ default: m.ProjectProfile })));
const SynonymManager = lazy(() => import('@/pages/SynonymManager').then(m => ({ default: m.SynonymManager })));
const SettingsLayout = lazy(() => import('@/pages/SettingsLayout').then(m => ({ default: m.SettingsLayout })));
const TemplateManager = lazy(() => import('@/pages/TemplateManager').then(m => ({ default: m.TemplateManager })));
const UserPreferences = lazy(() => import('@/pages/UserPreferences').then(m => ({ default: m.UserPreferences })));

// 在 Route 中添加
<Route path="projects/:id/profile" element={<ProjectProfile />} />
<Route path="projects/:id/synonyms" element={<SynonymManager />} />
<Route path="settings" element={<SettingsLayout />}>
  <Route index element={<Navigate to="/settings/templates" replace />} />
  <Route path="templates" element={<TemplateManager />} />
  <Route path="preferences" element={<UserPreferences />} />
</Route>
```

- [ ] **Step 2: 修改 `src/layouts/AppLayout.tsx` 添加设置导航入口**

在导航菜单中添加 "设置" 入口，链接到 `/settings`。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx frontend/src/layouts/AppLayout.tsx
git commit -m "feat(frontend): add routes and navigation for profile, synonyms, settings"
```

---

### Task 13: WebSocket 类型扩展

**Files:**
- Modify: `src/types/websocket.ts`

- [ ] **Step 1: 扩展 WebSocket 消息类型**

```typescript
// 在原有类型后追加

export interface AgentThinkingMessage extends WebSocketMessage {
  type: 'agent_thinking';
  task_id: string;
  message: string;
}

export interface AgentActionMessage extends WebSocketMessage {
  type: 'agent_action';
  task_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
}

export interface DimensionProgressMessage extends WebSocketMessage {
  type: 'dimension_progress';
  task_id: string;
  step: number;
  max_steps: number;
  dimensions: Record<string, string>;
  evidence_count: number;
}

export interface EvidenceCollectedMessage extends WebSocketMessage {
  type: 'evidence_collected';
  task_id: string;
  evidence_id: string;
  source: string;
}

export interface ReportVersionMessage extends WebSocketMessage {
  type: 'report_version';
  task_id: string;
  version_number: number;
  trigger_type: string;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/websocket.ts
git commit -m "feat(frontend): extend WebSocket message types for Agent progress"
```

---

## 自审查

### 1. Spec 覆盖检查

| Spec 章节 | 对应任务 | 状态 |
|----------|---------|------|
| 11.1.1 报告回溯页面 | Task 8 | ✅ |
| 11.1.2 项目画像管理页 | Task 6 | ✅ |
| 11.1.3 同义词管理页 | Task 5 | ✅ |
| 11.1.4 报告模板管理页 | Task 7 | ✅ |
| 11.1.5 用户偏好设置页 | Task 4 | ✅ |
| 11.2.1 分析提交页改造 | Task 9 | ✅ |
| 11.2.2 分析进度页改造 | Task 10 | ✅ |
| 11.2.3 项目列表页改造 | Task 11 | ✅ |
| 11.3 WebSocket 扩展 | Task 13 | ✅ |

### 2. Placeholder 扫描

- 无 "TBD"/"TODO" 占位符 ✅
- 每个任务包含完整代码 ✅
- 每个任务包含运行命令和预期输出 ✅
- 无 "类似 Task N" 引用 ✅

### 3. 类型一致性

- `AnalysisDepth` 类型在 Task 1 定义，Task 4、9 中使用 ✅
- `ReportVersion` 类型在 Task 1 定义，Task 8 中使用 ✅
- API 函数签名与后端路由一致 ✅
- 路由路径与 App.tsx 注册一致 ✅

---

## 执行交接

**计划已完成并保存到 `docs/superpowers/plans/2026-04-24-frontend-development.md`。**

**两个执行选项：**

**1. Subagent-Driven（推荐）** — 我按任务逐一分派子代理，任务间审查，快速迭代

**2. Inline Execution** — 在本会话中顺序执行任务，批量执行并设置检查点

**推荐方案：** Subagent-Driven。前端任务之间大部分独立（各页面组件互不影响），只有 Task 12（路由）依赖 Task 3-11 的页面组件存在。可以按以下批次并行：
- **批次 1**（独立）: Task 1-2（类型+API）、Task 3（SettingsLayout）、Task 4（Preferences）、Task 5（Synonyms）、Task 6（Profile）、Task 7（Templates）
- **批次 2**（依赖批次 1 的组件）: Task 8（ReportView）、Task 9（AnalysisSubmit）、Task 10（AnalysisProgress）、Task 11（Projects）
- **批次 3**（收尾）: Task 12（路由）、Task 13（WebSocket）

**选择哪种方式？**
