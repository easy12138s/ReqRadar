import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, Typography, Button, List, Tag, Space, theme } from 'antd';
import { motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell, PieChart, Pie
} from 'recharts';
import {
  ProjectOutlined, TagsOutlined, AppstoreOutlined,
  ExclamationCircleOutlined, PlusOutlined,
  FileTextOutlined, SendOutlined, RobotOutlined, TeamOutlined,
} from '@ant-design/icons';
import { getDashboardSummaries, type ProjectDashboardSummary } from '../api/projects';
import SkeletonStat from '../components/SkeletonStat';
import SkeletonCard from '../components/SkeletonCard';

const { Title, Text } = Typography;

export default function Dashboard() {
  const navigate = useNavigate();
  const { token } = theme.useToken();

  const { data: summaries = [], isLoading: loading, isError: error } = useQuery({
    queryKey: ['dashboard-summaries'],
    queryFn: getDashboardSummaries,
  });

  const projects = summaries.map((s: ProjectDashboardSummary) => ({
    id: s.id,
    name: s.name,
    termsCount: s.terms_count,
    modulesCount: s.modules_count,
    pendingChangesCount: s.pending_changes_count,
    updatedAt: s.updated_at,
  }));

  const totalTerms = projects.reduce((sum: number, p: typeof projects[number]) => sum + p.termsCount, 0);
  const totalModules = projects.reduce((sum: number, p: typeof projects[number]) => sum + p.modulesCount, 0);
  const totalPending = projects.reduce((sum: number, p: typeof projects[number]) => sum + p.pendingChangesCount, 0);

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
        <Title level={3} style={{ color: token.colorTextSecondary }}>还没有项目</Title>
        <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
          创建第一个项目开始使用需求分析
        </Text>
        <Button type="primary" icon={<PlusOutlined />} size="large" onClick={() => navigate('/projects')}>
          新建项目
        </Button>
      </div>
    );
  }

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } }
  };

  return (
    <motion.div variants={containerVariants} initial="hidden" animate="show">
      <motion.div variants={itemVariants}>
        <Title level={3} style={{ color: token.colorText, marginBottom: 4, fontWeight: 600 }}>
          欢迎回来
        </Title>
        <Text type="secondary" style={{ display: 'block', marginBottom: 32, fontSize: 15 }}>
          知识库总览
        </Text>
      </motion.div>

      {error && (
        <motion.div variants={itemVariants}>
          <Text type="warning" style={{ display: 'block', marginBottom: 16 }}>
            部分数据加载失败
          </Text>
        </motion.div>
      )}

      <Row gutter={[24, 24]} style={{ marginBottom: 32 }}>
        <Col xs={24} sm={12} lg={6}>
          <motion.div variants={itemVariants}>
            <Card size="small" className="flat-card" style={{ padding: '8px 4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <div style={{ padding: 12, borderRadius: 12, background: 'rgba(0,184,212,0.1)' }}>
                  <ProjectOutlined style={{ fontSize: 24, color: token.colorInfo }} />
                </div>
                <div>
                  <div style={{ fontSize: 13, color: token.colorTextSecondary, marginBottom: 4 }}>项目</div>
                  <div style={{ fontSize: 32, fontWeight: 700, color: token.colorText, lineHeight: 1 }}>{projects.length}</div>
                </div>
              </div>
            </Card>
          </motion.div>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <motion.div variants={itemVariants}>
            <Card size="small" className="flat-card" style={{ padding: '8px 4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <div style={{ padding: 12, borderRadius: 12, background: 'rgba(0,184,212,0.1)' }}>
                  <TagsOutlined style={{ fontSize: 24, color: token.colorPrimary }} />
                </div>
                <div>
                  <div style={{ fontSize: 13, color: token.colorTextSecondary, marginBottom: 4 }}>术语</div>
                  <div style={{ fontSize: 32, fontWeight: 700, color: token.colorText, lineHeight: 1 }}>{totalTerms}</div>
                </div>
              </div>
            </Card>
          </motion.div>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <motion.div variants={itemVariants}>
            <Card size="small" className="flat-card" style={{ padding: '8px 4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <div style={{ padding: 12, borderRadius: 12, background: 'rgba(0,200,83,0.1)' }}>
                  <AppstoreOutlined style={{ fontSize: 24, color: token.colorSuccess }} />
                </div>
                <div>
                  <div style={{ fontSize: 13, color: token.colorTextSecondary, marginBottom: 4 }}>模块</div>
                  <div style={{ fontSize: 32, fontWeight: 700, color: token.colorText, lineHeight: 1 }}>{totalModules}</div>
                </div>
              </div>
            </Card>
          </motion.div>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <motion.div variants={itemVariants}>
            <Card size="small" className="flat-card" style={{ padding: '8px 4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <div style={{ padding: 12, borderRadius: 12, background: 'rgba(255,171,0,0.1)' }}>
                  <ExclamationCircleOutlined style={{ fontSize: 24, color: token.colorWarning }} />
                </div>
                <div>
                  <div style={{ fontSize: 13, color: token.colorTextSecondary, marginBottom: 4 }}>待确认</div>
                  <div style={{ fontSize: 32, fontWeight: 700, color: token.colorText, lineHeight: 1 }}>{totalPending}</div>
                </div>
              </div>
            </Card>
          </motion.div>
        </Col>
      </Row>

      <Row gutter={[24, 24]} style={{ marginBottom: 32 }}>
        <Col xs={24} lg={12}>
          <motion.div variants={itemVariants} style={{ height: '100%' }}>
            <Card title="项目资产分布" className="flat-card" style={{ height: '100%' }}>
              {projects.length > 0 ? (
                <div style={{ height: 300, width: '100%' }}>
                  <ResponsiveContainer>
                    <BarChart data={projects.slice(0, 5)} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={token.colorBorderSecondary} vertical={false} />
                      <XAxis dataKey="name" stroke={token.colorTextSecondary} tick={{ fontSize: 12 }} />
                      <YAxis stroke={token.colorTextSecondary} tick={{ fontSize: 12 }} />
                      <RechartsTooltip 
                        contentStyle={{ backgroundColor: token.colorBgElevated, borderColor: token.colorBorderSecondary, borderRadius: 8 }}
                        itemStyle={{ color: token.colorText }}
                      />
                      <Bar dataKey="termsCount" name="术语" stackId="a" fill={token.colorPrimary} radius={[0, 0, 4, 4]} />
                      <Bar dataKey="modulesCount" name="模块" stackId="a" fill={token.colorSuccess} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', color: token.colorTextSecondary }}>
                  暂无数据
                </div>
              )}
            </Card>
          </motion.div>
        </Col>
        
        <Col xs={24} lg={12}>
          <motion.div variants={itemVariants} style={{ height: '100%' }}>
            <Card title="待确认变更分布" className="flat-card" style={{ height: '100%' }}>
              {totalPending > 0 ? (
                <div style={{ height: 300, width: '100%' }}>
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie
                        data={projects.filter((p: typeof projects[number]) => p.pendingChangesCount > 0)}
                        dataKey="pendingChangesCount"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={100}
                        innerRadius={60}
                        paddingAngle={5}
                      >
                        {projects.filter((p: typeof projects[number]) => p.pendingChangesCount > 0).map((_, index: number) => (
                          <Cell key={`cell-${index}`} fill={[token.colorWarning, token.colorError, token.colorPrimary, token.colorInfo][index % 4]} />
                        ))}
                      </Pie>
                      <RechartsTooltip 
                        contentStyle={{ backgroundColor: token.colorBgElevated, borderColor: token.colorBorderSecondary, borderRadius: 8 }}
                        itemStyle={{ color: token.colorText }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div style={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center', color: token.colorTextSecondary }}>
                  当前没有待确认的变更
                </div>
              )}
            </Card>
          </motion.div>
        </Col>
      </Row>

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={16}>
          <motion.div variants={itemVariants}>
            <Card title="项目总览" className="flat-card" style={{ height: '100%' }}>
              <List
                dataSource={projects}
                renderItem={(item: typeof projects[number]) => (
                  <List.Item
                    style={{ 
                      cursor: 'pointer', 
                      borderBottom: `1px solid ${token.colorBorderSecondary}`, 
                      padding: '16px 8px',
                      transition: 'background 0.2s',
                      borderRadius: 8
                    }}
                    onClick={() => navigate(`/projects/${item.id}`)}
                    className="dashboard-list-item"
                  >
                    <List.Item.Meta
                      title={<span style={{ color: token.colorText, fontSize: 16, fontWeight: 500 }}>{item.name}</span>}
                      description={
                        <Space size="middle" style={{ marginTop: 8 }}>
                          <Tag color="blue" bordered={false}>{item.termsCount} 术语</Tag>
                          <Tag color="green" bordered={false}>{item.modulesCount} 模块</Tag>
                          {item.pendingChangesCount > 0 && (
                            <Tag color="orange" bordered={false}>{item.pendingChangesCount} 待确认</Tag>
                          )}
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            </Card>
          </motion.div>
        </Col>
        
        <Col xs={24} lg={8}>
          <motion.div variants={itemVariants}>
            <Card title="快捷操作" className="flat-card">
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/projects')} block size="large">
                  新建项目
                </Button>
                <Button icon={<SendOutlined />} onClick={() => navigate('/analyses/submit')} block size="large">
                  提交分析
                </Button>
                <div style={{ height: 1, background: token.colorBorderSecondary, margin: '8px 0' }} />
                <Button type="text" icon={<RobotOutlined />} onClick={() => navigate('/settings/llm')} block style={{ textAlign: 'left' }}>
                  配置 LLM
                </Button>
                <Button type="text" icon={<FileTextOutlined />} onClick={() => navigate('/settings/templates')} block style={{ textAlign: 'left' }}>
                  管理模板
                </Button>
                <Button type="text" icon={<TeamOutlined />} onClick={() => navigate('/settings/users')} block style={{ textAlign: 'left' }}>
                  用户管理
                </Button>
              </Space>
            </Card>
          </motion.div>
        </Col>
      </Row>
      <style>{`
        .dashboard-list-item:hover {
          background: rgba(255, 255, 255, 0.04);
        }
      `}</style>
    </motion.div>
  );
}
