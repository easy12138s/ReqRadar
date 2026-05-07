import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, Typography, Button, List, Tag, Space, Modal, Form, Input, message } from 'antd';
import {
  ProjectOutlined, TagsOutlined, AppstoreOutlined,
  ExclamationCircleOutlined, PlusOutlined, ExperimentOutlined,
  FileTextOutlined, SettingOutlined, UserAddOutlined,
} from '@ant-design/icons';
import { getProjects, getProjectMemory } from '../api/projects';
import { getProjectProfile, getPendingChanges } from '../api/profile';
import { register } from '../api/auth';
import SkeletonStat from '../components/SkeletonStat';
import SkeletonCard from '../components/SkeletonCard';

const { Title, Text } = Typography;

interface ProjectSummary {
  id: string;
  name: string;
  termsCount: number;
  modulesCount: number;
  pendingChangesCount: number;
  updatedAt: string;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [error, setError] = useState(false);
  const [addUserOpen, setAddUserOpen] = useState(false);
  const [addUserLoading, setAddUserLoading] = useState(false);
  const [addUserForm] = Form.useForm();

  const handleAddUser = async (values: { email: string; display_name: string }) => {
    setAddUserLoading(true);
    try {
      await register({
        email: values.email,
        display_name: values.display_name,
        password: 'User12138%',
      });
      message.success(`用户 ${values.email} 创建成功，默认密码: User12138%`);
      setAddUserOpen(false);
      addUserForm.resetFields();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string; message?: string } }; message?: string };
      message.error(err.response?.data?.detail || err.response?.data?.message || err.message || '创建失败');
    } finally {
      setAddUserLoading(false);
    }
  };

  useEffect(() => {
    async function load() {
      try {
        const projectsData = await getProjects();
        const summaries: ProjectSummary[] = [];

        for (const p of projectsData) {
          try {
            const [memory, , pending] = await Promise.allSettled([
              getProjectMemory(p.id),
              getProjectProfile(p.id),
              getPendingChanges(p.id),
            ]);

            const termsCount = memory.status === 'fulfilled' && memory.value?.terminology
              ? (Array.isArray(memory.value.terminology) ? memory.value.terminology.length : 0)
              : 0;
            const modulesCount = memory.status === 'fulfilled' && memory.value?.modules
              ? (Array.isArray(memory.value.modules) ? memory.value.modules.length : 0)
              : 0;
            const pendingChangesCount = pending.status === 'fulfilled' && Array.isArray(pending.value)
              ? pending.value.filter(c => c.status === 'pending').length
              : 0;

            summaries.push({
              id: p.id,
              name: p.name,
              termsCount,
              modulesCount,
              pendingChangesCount,
              updatedAt: p.updated_at || p.created_at || '',
            });
          } catch {
            summaries.push({
              id: p.id, name: p.name,
              termsCount: 0, modulesCount: 0, pendingChangesCount: 0,
              updatedAt: p.updated_at || '',
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
          <SkeletonCard count={3} />
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
          <Button icon={<UserAddOutlined />} onClick={() => setAddUserOpen(true)}>
            添加用户
          </Button>
        </Space>
      </Card>

      <Modal
        title="添加用户"
        open={addUserOpen}
        onCancel={() => { setAddUserOpen(false); addUserForm.resetFields(); }}
        footer={null}
      >
        <Form form={addUserForm} layout="vertical" onFinish={handleAddUser}>
          <Form.Item
            label="邮箱"
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input placeholder="请输入邮箱" />
          </Form.Item>
          <Form.Item
            label="显示名称"
            name="display_name"
            rules={[{ required: true, message: '请输入显示名称' }]}
          >
            <Input placeholder="请输入显示名称" />
          </Form.Item>
          <div style={{ marginBottom: 16, padding: '8px 12px', background: 'rgba(0,212,255,0.08)', borderRadius: 8, fontSize: 13, color: '#00d4ff' }}>
            默认密码: <strong>User12138%</strong>
          </div>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={addUserLoading} block>
              确认添加
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
