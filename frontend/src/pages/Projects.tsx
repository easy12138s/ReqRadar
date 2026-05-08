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
  Dropdown,
} from 'antd';
import { useTranslation } from 'react-i18next';
import {
  CalendarOutlined,
  SyncOutlined,
  UploadOutlined,
  GithubOutlined,
  FolderOpenOutlined,
  DeleteOutlined,
  MoreOutlined,
  IdcardOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { Project, ProjectCreateFromLocal, ProjectCreateFromGit } from '@/types/api';
import { getProjects, createFromZip, createFromGit, createFromLocal, deleteProject } from '@/api/projects';
import { apiClient } from '@/api/client';

const { Title, Text, Paragraph } = Typography;

const SOURCE_TYPE_LABELS: Record<string, { text: string; color: string }> = {
  zip: { text: 'ZIP', color: 'orange' },
  git: { text: 'Git', color: 'green' },
    local: { text: t('projects.localPathLabel'), color: 'blue' },
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
  const { t } = useTranslation();

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const data = await getProjects();
      setProjects(data);
    } catch {
      message.error(t('projects.loadError'));
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
      message.success(t('projects.indexSuccess'));
    } catch {
      message.error(t('projects.indexError'));
    }
  };

  const handleCreateFromZip = async (values: { name: string; description: string }) => {
    if (!zipFile) {
      message.error(t('projects.zipRequired'));
      return;
    }
    setSubmitting(true);
    try {
      await createFromZip(values.name, values.description, zipFile);
      message.success(t('projects.createSuccess'));
      setZipModalVisible(false);
      zipForm.resetFields();
      setZipFile(null);
      fetchProjects();
    } catch {
      message.error(t('projects.createError'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateFromGit = async (values: ProjectCreateFromGit) => {
    setSubmitting(true);
    try {
      await createFromGit(values);
      message.success(t('projects.createSuccess'));
      setGitModalVisible(false);
      gitForm.resetFields();
      fetchProjects();
    } catch {
      message.error(t('projects.createError'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateFromLocal = async (values: ProjectCreateFromLocal) => {
    setSubmitting(true);
    try {
      await createFromLocal(values);
      message.success(t('projects.createSuccess'));
      setLocalModalVisible(false);
      localForm.resetFields();
      fetchProjects();
    } catch {
      message.error(t('projects.createError'));
    } finally {
      setSubmitting(false);
    }
  };

  const onProfile = (p: Project) => navigate(`/projects/${p.id}/profile`);
  const onSynonyms = (p: Project) => navigate(`/projects/${p.id}/synonyms`);
  const onRefreshProfile = (p: Project) => handleRegenerateProfile(p.id);
  const onDelete = (p: Project) => {
    Modal.confirm({
      title: t('projects.deleteConfirm'),
      content: t('projects.deleteContent', { name: p.name }),
      okText: t('common.delete'),
      okType: 'danger',
      cancelText: t('common.cancel'),
      onOk: async () => {
        try {
          await deleteProject(p.id);
          message.success(t('projects.deleteSuccess'));
          fetchProjects();
        } catch {
          message.error(t('projects.deleteError'));
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
          {t('projects.title')}
        </Title>
        <Space>
          <Button icon={<UploadOutlined />} onClick={() => setZipModalVisible(true)}>
            {t('projects.uploadZip')}
          </Button>
          <Button icon={<GithubOutlined />} onClick={() => setGitModalVisible(true)}>
            {t('projects.gitClone')}
          </Button>
          <Button type="primary" icon={<FolderOpenOutlined />} onClick={() => setLocalModalVisible(true)}>
            {t('projects.localPath')}
          </Button>
        </Space>
      </div>

      <Input.Search
        placeholder={t('projects.search')}
        allowClear
        style={{ marginBottom: 16, maxWidth: 400 }}
        onChange={(e) => setSearchText(e.target.value)}
      />

      {filtered.length === 0 ? (
        <Empty
          description={t('projects.empty')}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Space>
            <Button icon={<UploadOutlined />} onClick={() => setZipModalVisible(true)}>
              {t('projects.uploadZip')}
            </Button>
            <Button icon={<GithubOutlined />} onClick={() => setGitModalVisible(true)}>
              {t('projects.gitClone')}
            </Button>
            <Button type="primary" icon={<FolderOpenOutlined />} onClick={() => setLocalModalVisible(true)}>
              {t('projects.localPath')}
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
                extra={
                  <Dropdown menu={{
                    items: [
                      { key: 'profile', icon: <IdcardOutlined />, label: t('projects.actions.profile') },
                      { key: 'synonyms', icon: <SwapOutlined />, label: t('projects.actions.synonyms') },
                      { key: 'index', icon: <SyncOutlined />, label: t('projects.actions.index') },
                      { type: 'divider' },
                      { key: 'delete', icon: <DeleteOutlined />, label: t('projects.actions.delete'), danger: true },
                    ],
                    onClick: ({ key }) => {
                      if (key === 'profile') onProfile(project);
                      else if (key === 'synonyms') onSynonyms(project);
                      else if (key === 'index') onRefreshProfile(project);
                      else if (key === 'delete') onDelete(project);
                    }
                  }} trigger={['click']}>
                    <Button type="text" size="small" icon={<MoreOutlined />} />
                  </Dropdown>
                }
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
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title={t('projects.zipTitle')}
        open={zipModalVisible}
        onCancel={() => { setZipModalVisible(false); zipForm.resetFields(); setZipFile(null); }}
        footer={null}
      >
        <Form form={zipForm} onFinish={handleCreateFromZip} layout="vertical">
          <Form.Item
            label={t('projects.name')}
            name="name"
            rules={[
              { required: true, message: t('projects.nameRequired') },
              { pattern: /^[a-zA-Z0-9_-]{1,64}$/, message: t('projects.namePattern') },
            ]}
          >
            <Input placeholder="my-project" />
          </Form.Item>
          <Form.Item label={t('projects.description')} name="description">
            <Input.TextArea rows={3} placeholder={t('projects.descPlaceholder')} />
          </Form.Item>
          <Form.Item
            label={t('projects.zipFile')}
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
              <Button icon={<UploadOutlined />}>{t('projects.selectZip')}</Button>
            </Upload>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>
              {t('projects.create')}
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={t('projects.gitTitle')}
        open={gitModalVisible}
        onCancel={() => { setGitModalVisible(false); gitForm.resetFields(); }}
        footer={null}
      >
        <Form form={gitForm} onFinish={handleCreateFromGit} layout="vertical">
          <Form.Item
            label={t('projects.name')}
            name="name"
            rules={[
              { required: true, message: t('projects.nameRequired') },
              { pattern: /^[a-zA-Z0-9_-]{1,64}$/, message: t('projects.namePattern') },
            ]}
          >
            <Input placeholder="my-project" />
          </Form.Item>
          <Form.Item label={t('projects.description')} name="description">
            <Input.TextArea rows={3} placeholder={t('projects.descPlaceholder')} />
          </Form.Item>
          <Form.Item
            label={t('projects.gitUrl')}
            name="git_url"
            rules={[{ required: true, message: t('projects.gitUrlRequired') }]}
          >
            <Input placeholder="https://github.com/user/repo.git" />
          </Form.Item>
          <Form.Item label={t('projects.branch')} name="branch">
            <Input placeholder="main" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>
              {t('projects.cloneAndCreate')}
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={t('projects.localTitle')}
        open={localModalVisible}
        onCancel={() => { setLocalModalVisible(false); localForm.resetFields(); }}
        footer={null}
      >
        <Form form={localForm} onFinish={handleCreateFromLocal} layout="vertical">
          <Form.Item
            label={t('projects.name')}
            name="name"
            rules={[
              { required: true, message: t('projects.nameRequired') },
              { pattern: /^[a-zA-Z0-9_-]{1,64}$/, message: t('projects.namePattern') },
            ]}
          >
            <Input placeholder="my-project" />
          </Form.Item>
          <Form.Item label={t('projects.description')} name="description">
            <Input.TextArea rows={3} placeholder={t('projects.descPlaceholder')} />
          </Form.Item>
          <Form.Item
            label={t('projects.localPathLabel')}
            name="local_path"
            rules={[{ required: true, message: t('projects.localPathRequired') }]}
          >
            <Input placeholder="/path/to/your/project" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>
              {t('projects.create')}
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
