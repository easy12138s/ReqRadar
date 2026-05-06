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
} from '@/types/api';
import { getProject, updateProject, getProjectMemory, getProjectFiles, deleteProject } from '@/api/projects';

const { Title, Paragraph } = Typography;

const SOURCE_TYPE_LABELS: Record<string, { text: string; color: string }> = {
  zip: { text: 'ZIP', color: 'orange' },
  git: { text: 'Git', color: 'green' },
  local: { text: '本地路径', color: 'blue' },
};

function buildAntTree(nodes: FileTreeNode[]): import('antd').TreeDataNode[] {
  return nodes.map((node) => ({
    key: node.path,
    title: node.name,
    icon: node.type === 'directory' ? <FolderOutlined /> : <FileOutlined />,
    children: node.children ? buildAntTree(node.children) : undefined,
  }));
}

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

  useEffect(() => {
    fetchData();
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
  ];

  return (
    <div>
      <Title level={3}>{project.name}</Title>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}
