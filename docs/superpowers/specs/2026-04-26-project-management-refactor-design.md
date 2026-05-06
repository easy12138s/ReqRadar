# Project Management Refactor Design

> 日期：2026-04-26 | 状态：已确认

## 目标

重构项目管理模块，支持独立文件空间、ZIP 上传、Git 克隆、本地路径导入，实现项目隔离和统一目录结构。

## 目录结构

```
~/.reqradar/data/<project_name>/       ← web.data_root + project.name
├── project_code/                      ← 代码文件（解压/克隆/复制）
│   └── (可能嵌套一层子目录，如 cool-agent/)
├── requirements/                      ← 需求文件上传
├── index/                             ← 索引（code_graph.json + vectorstore/）
├── memory/                            ← 项目记忆
├── profile.yaml                       ← 项目画像
└── project.zip                        ← zip 备份（仅 zip 来源）
```

`project_code/` 下读取代码时需自动检测实际代码根目录：若只有一个子目录且是目录，则用该子目录；否则用 `project_code/` 本身。

## 配置

`.reqradar.yaml` 新增：

```yaml
web:
  data_root: ~/.reqradar/data   # 支持 ~ 展开
```

## Project 模型变更

**新增字段**：
- `source_type: String(20)` — `"zip"` / `"git"` / `"local"`
- `source_url: String(1024)` — git 仓库地址或 zip 原始文件名

**移除字段**：
- `repo_path`、`index_path`、`docs_path` — 改为通过 `ProjectFileService` 自动计算

**路径通过 service 计算**（不存 DB）：
- `project_path` — `data_root / name`
- `code_path` — `data_root / name / project_code`（经 detect_code_root）
- `index_path` — `data_root / name / index`
- `requirements_path` — `data_root / name / requirements`
- `memory_path` — `data_root / name / memory`

**项目名验证**：`^[a-zA-Z0-9_-]{1,64}$`，同 owner 下不可重复。

## 后端新增：ProjectFileService

文件：`src/reqradar/web/services/project_file_service.py`

| 方法 | 功能 |
|:---|:---|
| `get_project_path(name)` | 返回 `data_root / name` |
| `create_project_dirs(name)` | 创建所有子目录 |
| `extract_zip(name, zip_bytes)` | 解压到 `project_code/`，保留 zip 备份 |
| `clone_git(name, url, branch=None)` | git clone 到 `project_code/`，检测 git 可用性 |
| `detect_code_root(name)` | 检测实际代码根目录 |
| `delete_project_files(name)` | 删除整个项目目录 |
| `get_file_tree(name)` | 返回项目文件树 |
| `is_git_available()` | 检测系统是否有 git |

## API 变更

**新增端点**：

| 端点 | 方法 | 功能 |
|:---|:---|:---|
| `/api/projects/from-zip` | POST | 上传 zip 创建项目（multipart: name, description, file） |
| `/api/projects/from-git` | POST | Git 克隆创建项目（JSON: name, description, git_url, branch） |
| `/api/projects/from-local` | POST | 本地路径创建项目（JSON: name, description, local_path） |
| `/api/projects/{id}/files` | GET | 浏览项目文件树 |

**修改端点**：
- `GET /api/projects` / `GET /api/projects/{id}` — 响应新增 `source_type`、`source_url`
- `POST /api/projects` — 移除（统一用三个新端点创建）
- `POST /api/projects/{id}/index` — 适配新路径

## 前端变更

**Projects 页面**：三个创建入口按钮
- 上传 ZIP — Modal: 项目名、描述、ZIP 文件
- Git 克隆 — Modal: 项目名、描述、Git URL、分支
- 本地路径 — Modal: 项目名、描述、本地路径

**ProjectDetail 页面**：文件浏览器 + 索引状态

**类型更新**：
```typescript
interface Project {
  id: number;
  name: string;
  description: string;
  source_type: 'zip' | 'git' | 'local';
  source_url: string;
  owner_id: number;
  created_at: string;
  updated_at: string;
}
```

## 分析流程集成

```python
svc = ProjectFileService(config)
repo_path = svc.detect_code_root(project.name)
index_path = str(svc.get_project_path(project.name) / "index")
memory_path = str(svc.get_project_path(project.name) / "memory")
```

PathSandbox `allowed_root` 设为 `project_code/` 目录。

## Git 环境检测

通过 `shutil.which("git")` 检测。不可用时隐藏 Git 克隆入口，提示"系统未安装 Git，可使用 ZIP 上传替代"。
