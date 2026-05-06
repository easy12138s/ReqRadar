import { useEffect, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Typography,
  Empty,
  Spin,
  Tag,
  message,
  Modal,
  Form,
  Input,
  Upload,
  Space,
} from 'antd';
import {
  CodeOutlined,
  CalendarOutlined,
  ProfileOutlined,
  SyncOutlined,
  BookOutlined,
  UploadOutlined,
  GithubOutlined,
  FolderOpenOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { useNavigate, Link } from 'react-router-dom';
import type { Project, ProjectCreateFromLocal, ProjectCreateFromGit } from '@/types/api';
import { getProjects, createFromZip, createFromGit, createFromLocal, deleteProject } from '@/api/projects';
import { apiClient } from '@/api/client';

const { Title, Text, Paragraph } = Typography;

const SOURCE_TYPE_LABELS: Record<string, { text: string; color: string }> = {
  zip: { text: 'ZIP', color: 'orange' },
  git: { text: 'Git', color: 'green' },
  local: { text: '本地路径', color: 'blue' },
};

export function Projects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [zipModalVisible, setZipModalVisible] = useState(false);
  const [gitModalVisible, setGitModalVisible] = useState(false);
  const [localModalVisible, setLocalModalVisible] = useState(false);
  const [zipForm] = Form.useForm();
  const [gitForm] = Form.useForm();
  const [localForm] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [searchText, setSearchText] = useState('');
  const navigate = useNavigate();

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const data = await getProjects();
      setProjects(data);
    } catch {
      message.error('加载项目列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleRegenerateProfile = async (projectId: string) => {
    try {
      await apiClient.post(`/projects/${projectId}/index`);
      message.success('画像更新已触发');
    } catch {
      message.error('画像更新失败');
    }
  };

  const handleCreateFromZip = async (values: { name: string; description: string }) => {
    if (!zipFile) {
      message.error('请选择 ZIP 文件');
      return;
    }
    setSubmitting(true);
    try {
      await createFromZip(values.name, values.description, zipFile);
      message.success('项目创建成功');
      setZipModalVisible(false);
      zipForm.resetFields();
      setZipFile(null);
      fetchProjects();
    } catch {
      message.error('创建项目失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateFromGit = async (values: ProjectCreateFromGit) => {
    setSubmitting(true);
    try {
      await createFromGit(values);
      message.success('项目创建成功');
      setGitModalVisible(false);
      gitForm.resetFields();
      fetchProjects();
    } catch {
      message.error('创建项目失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateFromLocal = async (values: ProjectCreateFromLocal) => {
    setSubmitting(true);
    try {
      await createFromLocal(values);
      message.success('项目创建成功');
      setLocalModalVisible(false);
      localForm.resetFields();
      fetchProjects();
    } catch {
      message.error('创建项目失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteProject = (projectId: string, projectName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除项目「${projectName}」吗？此操作不可撤销。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteProject(projectId);
          message.success('项目已删除');
          fetchProjects();
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(searchText.toLowerCase())
  );

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          项目
        </Title>
        <Space>
          <Button icon={<UploadOutlined />} onClick={() => setZipModalVisible(true)}>
            上传 ZIP
          </Button>
          <Button icon={<GithubOutlined />} onClick={() => setGitModalVisible(true)}>
            Git 克隆
          </Button>
          <Button type="primary" icon={<FolderOpenOutlined />} onClick={() => setLocalModalVisible(true)}>
            本地路径
          </Button>
        </Space>
      </div>

      <Input.Search
        placeholder="搜索项目..."
        allowClear
        style={{ marginBottom: 16, maxWidth: 400 }}
        onChange={(e) => setSearchText(e.target.value)}
      />

      {filtered.length === 0 ? (
        <Empty
          description="暂无项目"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Space>
            <Button icon={<UploadOutlined />} onClick={() => setZipModalVisible(true)}>
              上传 ZIP
            </Button>
            <Button icon={<GithubOutlined />} onClick={() => setGitModalVisible(true)}>
              Git 克隆
            </Button>
            <Button type="primary" icon={<FolderOpenOutlined />} onClick={() => setLocalModalVisible(true)}>
              本地路径
            </Button>
          </Space>
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {filtered.map((project) => (
            <Col xs={24} sm={12} lg={8} key={project.id}>
              <Card
                hoverable
                onClick={() => navigate(`/projects/${project.id}`)}
                title={project.name}
                extra={<CodeOutlined />}
              >
                <Paragraph ellipsis={{ rows: 2 }}>{project.description}</Paragraph>
                <div style={{ marginTop: 12 }}>
                  <Tag color={SOURCE_TYPE_LABELS[project.source_type]?.color || 'default'}>
                    {SOURCE_TYPE_LABELS[project.source_type]?.text || project.source_type}
                  </Tag>
                </div>
                <div style={{ marginTop: 12 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    <CalendarOutlined />{' '}
                    {new Date(project.created_at).toLocaleDateString()}
                  </Text>
                </div>
                <div style={{ marginTop: 12 }}>
                  <Space size="small" onClick={(e) => e.stopPropagation()}>
                    <Link to={`/projects/${project.id}/profile`}>
                      <Button icon={<ProfileOutlined />} size="small">画像管理</Button>
                    </Link>
                    <Link to={`/projects/${project.id}/synonyms`}>
                      <Button icon={<BookOutlined />} size="small">同义词</Button>
                    </Link>
                    <Button icon={<SyncOutlined />} size="small" onClick={(e) => { e.stopPropagation(); handleRegenerateProfile(project.id); }}>更新画像</Button>
                    <Button icon={<DeleteOutlined />} size="small" danger onClick={(e) => handleDeleteProject(project.id, project.name, e)}>删除</Button>
                  </Space>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="上传 ZIP 创建项目"
        open={zipModalVisible}
        onCancel={() => { setZipModalVisible(false); zipForm.resetFields(); setZipFile(null); }}
        footer={null}
      >
        <Form form={zipForm} onFinish={handleCreateFromZip} layout="vertical">
          <Form.Item
            label="项目名称"
            name="name"
            rules={[
              { required: true, message: '请输入项目名称' },
              { pattern: /^[a-zA-Z0-9_-]{1,64}$/, message: '仅支持字母、数字、下划线、连字符，1-64字符' },
            ]}
          >
            <Input placeholder="my-project" />
          </Form.Item>
          <Form.Item label="项目描述" name="description">
            <Input.TextArea rows={3} placeholder="请输入项目描述" />
          </Form.Item>
          <Form.Item
            label="ZIP 文件"
            required
          >
            <Upload
              beforeUpload={(file) => {
                setZipFile(file);
                return false;
              }}
              accept=".zip"
              maxCount={1}
              onRemove={() => setZipFile(null)}
            >
              <Button icon={<UploadOutlined />}>选择 ZIP 文件</Button>
            </Upload>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>
              创建
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Git 克隆创建项目"
        open={gitModalVisible}
        onCancel={() => { setGitModalVisible(false); gitForm.resetFields(); }}
        footer={null}
      >
        <Form form={gitForm} onFinish={handleCreateFromGit} layout="vertical">
          <Form.Item
            label="项目名称"
            name="name"
            rules={[
              { required: true, message: '请输入项目名称' },
              { pattern: /^[a-zA-Z0-9_-]{1,64}$/, message: '仅支持字母、数字、下划线、连字符，1-64字符' },
            ]}
          >
            <Input placeholder="my-project" />
          </Form.Item>
          <Form.Item label="项目描述" name="description">
            <Input.TextArea rows={3} placeholder="请输入项目描述" />
          </Form.Item>
          <Form.Item
            label="Git 仓库地址"
            name="git_url"
            rules={[{ required: true, message: '请输入 Git 仓库地址' }]}
          >
            <Input placeholder="https://github.com/user/repo.git" />
          </Form.Item>
          <Form.Item label="分支（可选）" name="branch">
            <Input placeholder="main" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>
              克隆并创建
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="本地路径创建项目"
        open={localModalVisible}
        onCancel={() => { setLocalModalVisible(false); localForm.resetFields(); }}
        footer={null}
      >
        <Form form={localForm} onFinish={handleCreateFromLocal} layout="vertical">
          <Form.Item
            label="项目名称"
            name="name"
            rules={[
              { required: true, message: '请输入项目名称' },
              { pattern: /^[a-zA-Z0-9_-]{1,64}$/, message: '仅支持字母、数字、下划线、连字符，1-64字符' },
            ]}
          >
            <Input placeholder="my-project" />
          </Form.Item>
          <Form.Item label="项目描述" name="description">
            <Input.TextArea rows={3} placeholder="请输入项目描述" />
          </Form.Item>
          <Form.Item
            label="本地路径"
            name="local_path"
            rules={[{ required: true, message: '请输入本地路径' }]}
          >
            <Input placeholder="/path/to/your/project" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>
              创建
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
