import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Tabs,
  Typography,
  Descriptions,
  Tag,
  Table,
  Spin,
  Empty,
  Button,
  Form,
  Input,
  message,
  Modal,
  Tree,
} from 'antd';
import {
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
  FolderOutlined,
  FileOutlined,
  DeleteOutlined,
  ExperimentOutlined,
  SendOutlined,
  InboxOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import type {
  Project,
  ProjectMemory,
  ProjectUpdate,
  TermEntry,
  ModuleEntry,
  TeamMember,
  HistoryEntry,
  FileTreeNode,
  RequirementRelease,
} from '@/types/api';
import { getProject, updateProject, getProjectMemory, getProjectFiles, deleteProject } from '@/api/projects';
import { apiClient } from '@/api/client';
import { listReleases, publishRelease, archiveRelease, deleteRelease } from '@/api/releases';

const { Title, Paragraph } = Typography;

const SOURCE_TYPE_LABELS: Record<string, { text: string; color: string }> = {
  zip: { text: 'ZIP', color: 'orange' },
  git: { text: 'Git', color: 'green' },
  local: { text: '本地路径', color: 'blue' },
};

const RELEASE_STATUS_LABELS: Record<string, { text: string; color: string }> = {
  draft: { text: '草稿', color: 'default' },
  published: { text: '已发布', color: 'green' },
  archived: { text: '已归档', color: 'orange' },
};

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [project, setProject] = useState<Project | null>(null);
  const [memory, setMemory] = useState<ProjectMemory | null>(null);
  const [fileTree, setFileTree] = useState<FileTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [releases, setReleases] = useState<RequirementRelease[]>([]);
  const [releasesLoading, setReleasesLoading] = useState(false);

  const fetchData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [projectData, memoryData, filesData] = await Promise.all([
        getProject(id),
        getProjectMemory(id),
        getProjectFiles(id).catch(() => []),
      ]);
      setProject(projectData);
      setMemory(memoryData);
      setFileTree(filesData);
      form.setFieldsValue(projectData);
    } catch {
      message.error('加载项目失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchReleases = async () => {
    if (!id) return;
    setReleasesLoading(true);
    try {
      const data = await listReleases({ project_id: Number(id) });
      setReleases(data);
    } catch {
      message.error('加载需求版本失败');
    } finally {
      setReleasesLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    fetchReleases();
  }, [id]);

  const handleSave = async (values: ProjectUpdate) => {
    if (!id) return;
    setSaving(true);
    try {
      const updated = await updateProject(id, values);
      setProject(updated);
      setEditing(false);
      message.success('项目更新成功');
    } catch {
      message.error('更新项目失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = () => {
    if (!id) return;
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除项目「${project?.name}」吗？此操作不可撤销。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteProject(id);
          message.success('项目已删除');
          navigate('/projects');
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const handlePublishRelease = async (releaseId: number) => {
    try {
      await publishRelease(releaseId);
      message.success('发布成功');
      fetchReleases();
    } catch {
      message.error('发布失败');
    }
  };

  const handleArchiveRelease = async (releaseId: number) => {
    try {
      await archiveRelease(releaseId);
      message.success('归档成功');
      fetchReleases();
    } catch {
      message.error('归档失败');
    }
  };

  const handleDeleteRelease = async (releaseId: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除此需求版本吗？仅草稿状态可删除。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteRelease(releaseId);
          message.success('删除成功');
          fetchReleases();
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const [indexing, setIndexing] = useState(false);
  const handleRebuildIndex = async () => {
    if (!id) return;
    setIndexing(true);
    try {
      await apiClient.post(`/projects/${id}/index`);
      message.success('索引重建已启动，请稍候');
    } catch {
      message.error('索引重建触发失败');
    } finally {
      setIndexing(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!project) {
    return <Empty description="项目未找到" />;
  }

  const overviewContent = editing ? (
    <Form
      form={form}
      onFinish={handleSave}
      layout="vertical"
      initialValues={project}
    >
      <Form.Item
        label="项目名称"
        name="name"
        rules={[{ required: true }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        label="项目描述"
        name="description"
      >
        <Input.TextArea rows={4} />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={saving} icon={<SaveOutlined />}>
          保存
        </Button>
        <Button
          icon={<CloseOutlined />}
          onClick={() => {
            setEditing(false);
            form.resetFields();
          }}
          style={{ marginLeft: 8 }}
        >
          取消
        </Button>
      </Form.Item>
    </Form>
  ) : (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>
          编辑
        </Button>
        <Button
          icon={<DeleteOutlined />}
          danger
          onClick={handleDelete}
          style={{ marginLeft: 8 }}
        >
          删除
        </Button>
        <Button
          type="primary"
          icon={<ExperimentOutlined />}
          onClick={() => navigate(`/analyses/submit?projectId=${id}`)}
          style={{ marginLeft: 8 }}
        >
          提交分析
        </Button>
        <Button
          icon={<SyncOutlined />}
          loading={indexing}
          onClick={handleRebuildIndex}
          style={{ marginLeft: 8 }}
        >
          重建索引
        </Button>
      </div>
      <Descriptions bordered column={1}>
        <Descriptions.Item label="项目名称">{project.name}</Descriptions.Item>
        <Descriptions.Item label="项目描述">
          <Paragraph>{project.description}</Paragraph>
        </Descriptions.Item>
        <Descriptions.Item label="来源类型">
          <Tag color={SOURCE_TYPE_LABELS[project.source_type]?.color || 'default'}>
            {SOURCE_TYPE_LABELS[project.source_type]?.text || project.source_type}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="来源地址">{project.source_url || '-'}</Descriptions.Item>
        <Descriptions.Item label="创建时间">
          {new Date(project.created_at).toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="更新时间">
          {new Date(project.updated_at).toLocaleString()}
        </Descriptions.Item>
      </Descriptions>
    </div>
  );

  const tabItems = [
    {
      key: 'overview',
      label: '概览',
      children: overviewContent,
    },
    {
      key: 'files',
      label: '文件浏览',
      children: fileTree.length > 0 ? (
        <Tree
          showIcon
          defaultExpandedKeys={[fileTree[0]?.path]}
          treeData={buildAntTree(fileTree)}
        />
      ) : (
        <Empty description="暂无文件" />
      ),
    },
    {
      key: 'memory',
      label: '知识库',
      children: (
        <Tabs
          style={{ marginTop: 12 }}
          items={[
            {
              key: 'terminology',
              label: '术语',
              children: (
                <Table<TermEntry>
                  dataSource={memory?.terminology || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: '术语', dataIndex: 'term', key: 'term' },
                    { title: '定义', dataIndex: 'definition', key: 'definition' },
                    { title: '上下文', dataIndex: 'context', key: 'context' },
                  ]}
                  locale={{ emptyText: '暂无术语记录' }}
                />
              ),
            },
            {
              key: 'modules',
              label: '模块',
              children: (
                <Table<ModuleEntry>
                  dataSource={memory?.modules || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: '名称', dataIndex: 'name', key: 'name' },
                    { title: '描述', dataIndex: 'description', key: 'description' },
                    {
                      title: '职责',
                      dataIndex: 'responsibilities',
                      key: 'responsibilities',
                      render: (v: string[]) => v?.map((r) => <Tag key={r}>{r}</Tag>) || '-',
                    },
                  ]}
                  locale={{ emptyText: '暂无模块记录' }}
                />
              ),
            },
            {
              key: 'team',
              label: '团队',
              children: (
                <Table<TeamMember>
                  dataSource={memory?.team || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: '姓名', dataIndex: 'name', key: 'name' },
                    { title: '角色', dataIndex: 'role', key: 'role' },
                    {
                      title: '专长',
                      dataIndex: 'expertise',
                      key: 'expertise',
                      render: (v: string[]) => v?.map((e) => <Tag key={e}>{e}</Tag>) || '-',
                    },
                  ]}
                  locale={{ emptyText: '暂无团队成员' }}
                />
              ),
            },
            {
              key: 'history',
              label: '历史',
              children: (
                <Table<HistoryEntry>
                  dataSource={memory?.history || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: '事件', dataIndex: 'event', key: 'event' },
                    { title: '详情', dataIndex: 'details', key: 'details' },
                    {
                      title: '时间',
                      dataIndex: 'timestamp',
                      key: 'timestamp',
                      render: (v: string) => new Date(v).toLocaleString(),
                    },
                  ]}
                  locale={{ emptyText: '暂无历史记录' }}
                />
              ),
            },
      ]}
      />
      ),
    },
    {
      key: 'releases',
      label: '需求版本',
      children: (
        <Table<RequirementRelease>
          dataSource={releases}
          rowKey="id"
          loading={releasesLoading}
          pagination={false}
          columns={[
            { title: '版本代号', dataIndex: 'release_code', key: 'release_code' },
            { title: '版本', dataIndex: 'version', key: 'version', width: 60 },
            { title: '标题', dataIndex: 'title', key: 'title' },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              width: 100,
              render: (status: string) => (
                <Tag color={RELEASE_STATUS_LABELS[status]?.color || 'default'}>
                  {RELEASE_STATUS_LABELS[status]?.text || status}
                </Tag>
              ),
            },
            {
              title: '发布时间',
              dataIndex: 'published_at',
              key: 'published_at',
              width: 180,
              render: (v: string | null) => (v ? new Date(v).toLocaleString() : '-'),
            },
            {
              title: '操作',
              key: 'actions',
              width: 180,
              render: (_: unknown, record: RequirementRelease) => (
                <>
                  {record.status === 'draft' && (
                    <Button
                      type="link"
                      size="small"
                      icon={<SendOutlined />}
                      onClick={() => handlePublishRelease(record.id)}
                    >
                      发布
                    </Button>
                  )}
                  {record.status === 'published' && (
                    <Button
                      type="link"
                      size="small"
                      icon={<InboxOutlined />}
                      onClick={() => handleArchiveRelease(record.id)}
                    >
                      归档
                    </Button>
                  )}
                  {record.status === 'draft' && (
                    <Button
                      type="link"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleDeleteRelease(record.id)}
                    >
                      删除
                    </Button>
                  )}
                </>
              ),
            },
          ]}
          locale={{ emptyText: '暂无需求版本' }}
        />
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>{project.name}</Title>
      <Card style={{ background: '#111827', border: '1px solid #1e293b' }}>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}

function buildAntTree(nodes: FileTreeNode[]): import('antd').TreeDataNode[] {
  return nodes.map((node) => ({
    key: node.path,
    title: node.name,
    icon: node.type === 'directory' ? <FolderOutlined /> : <FileOutlined />,
    children: node.children ? buildAntTree(node.children) : undefined,
  }));
}
