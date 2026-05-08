import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, Typography, Button, List, Tag, Space, theme } from 'antd';
import { useTranslation } from 'react-i18next';
import {
  ProjectOutlined, TagsOutlined, AppstoreOutlined,
  ExclamationCircleOutlined, PlusOutlined,
  FileTextOutlined, SendOutlined, RobotOutlined, TeamOutlined,
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
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [error, setError] = useState(false);
  const { token } = theme.useToken();

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
        <ProjectOutlined style={{ fontSize: 64, color: token.colorBorderSecondary, marginBottom: 16 }} />
        <Title level={3} style={{ color: token.colorTextSecondary }}>{t('dashboard.empty')}</Title>
        <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
          {t('dashboard.emptyDesc')}
        </Text>
        <Button type="primary" icon={<PlusOutlined />} size="large" onClick={() => navigate('/projects')}>
          {t('dashboard.newProject')}
        </Button>
      </div>
    );
  }

  return (
    <div>
      <Title level={3} style={{ color: token.colorText, marginBottom: 4 }}>
        {t('dashboard.welcome')}
      </Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        {t('dashboard.overview')}
      </Text>

      {error && (
        <Text type="warning" style={{ display: 'block', marginBottom: 16 }}>
          {t('dashboard.loadError')}
        </Text>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="flat-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <ProjectOutlined style={{ fontSize: 22, color: token.colorInfo }} />
              <div>
                <div style={{ fontSize: 12, color: token.colorTextDescription }}>{t('dashboard.stats.projects')}</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: token.colorText }}>{projects.length}</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="flat-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <TagsOutlined style={{ fontSize: 22, color: token.colorPrimary }} />
              <div>
                <div style={{ fontSize: 12, color: token.colorTextDescription }}>{t('dashboard.stats.terms')}</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: token.colorText }}>{totalTerms}</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="flat-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <AppstoreOutlined style={{ fontSize: 22, color: token.colorSuccess }} />
              <div>
                <div style={{ fontSize: 12, color: token.colorTextDescription }}>{t('dashboard.stats.modules')}</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: token.colorText }}>{totalModules}</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card size="small" className="flat-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <ExclamationCircleOutlined style={{ fontSize: 22, color: token.colorWarning }} />
              <div>
                <div style={{ fontSize: 12, color: token.colorTextDescription }}>{t('dashboard.stats.pending')}</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: token.colorText }}>{totalPending}</div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <Card title={t('dashboard.projectOverview')} className="flat-card" style={{ marginBottom: 24 }}>
        <List
          dataSource={projects}
          renderItem={(item) => (
            <List.Item
              style={{ cursor: 'pointer', borderBottom: `1px solid ${token.colorBorderSecondary}`, padding: '12px 0' }}
              onClick={() => navigate(`/projects/${item.id}`)}
            >
              <List.Item.Meta
                title={<span style={{ color: token.colorTextHeading }}>{item.name}</span>}
                description={
                  <Space size="middle">
                    <Tag color="blue">{item.termsCount}{t('dashboard.termsSuffix')}</Tag>
                    <Tag color="green">{item.modulesCount}{t('dashboard.modulesSuffix')}</Tag>
                    {item.pendingChangesCount > 0 && (
                      <Tag color="orange">{item.pendingChangesCount}{t('dashboard.pendingSuffix')}</Tag>
                    )}
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Card>

      <Card title={t('dashboard.quickActions')} className="flat-card">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space wrap>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/projects')}>
              {t('dashboard.newProject')}
            </Button>
            <Button icon={<SendOutlined />} onClick={() => navigate('/analyses/submit')}>
              {t('dashboard.submitAnalysis')}
            </Button>
          </Space>
          <Space wrap>
            <Button icon={<RobotOutlined />} onClick={() => navigate('/settings/llm')}>
              {t('dashboard.configLLM')}
            </Button>
            <Button icon={<FileTextOutlined />} onClick={() => navigate('/settings/templates')}>
              {t('dashboard.manageTemplates')}
            </Button>
            <Button icon={<TeamOutlined />} onClick={() => navigate('/settings/users')}>
              {t('dashboard.manageUsers')}
            </Button>
          </Space>
        </Space>
      </Card>
    </div>
  );
}
