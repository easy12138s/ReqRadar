import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, Typography, Button, List, Tag, Space } from 'antd';
import {
  ProjectOutlined, TagsOutlined, AppstoreOutlined,
  ExclamationCircleOutlined, PlusOutlined, ExperimentOutlined,
  FileTextOutlined, SettingOutlined,
} from '@ant-design/icons';
import { getProjects, getProjectMemory } from '../api/projects';
import { getProjectProfile, getPendingChanges } from '../api/profile';
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

  useEffect(() => {
    async function load() {
      try {
        const projectsData = await getProjects();
        const summaries: ProjectSummary[] = [];

        for (const p of projectsData) {
          try {
            const [memory, profile, pending] = await Promise.allSettled([
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
        </Space>
      </Card>
    </div>
  );
}
