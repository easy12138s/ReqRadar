import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, Typography } from 'antd';
import {
  RobotOutlined, FileTextOutlined, UserOutlined, TeamOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;

const items = [
  { key: '/settings/llm', icon: <RobotOutlined style={{ fontSize: 32, color: '#00b8d4' }} />, title: 'LLM 配置', desc: 'API 密钥、模型、参数' },
  { key: '/settings/templates', icon: <FileTextOutlined style={{ fontSize: 32, color: '#7c3aed' }} />, title: '报告模板', desc: '管理分析报告模板' },
  { key: '/settings/preferences', icon: <UserOutlined style={{ fontSize: 32, color: '#10b981' }} />, title: '偏好设置', desc: '分析与展示偏好' },
  { key: '/settings/users', icon: <TeamOutlined style={{ fontSize: 32, color: '#f59e0b' }} />, title: '用户管理', desc: '添加/管理用户与角色' },
];

export default function SettingsPage() {
  const navigate = useNavigate();

  return (
    <div>
      <Title level={4} style={{ color: '#f0f6fc' }}>设置</Title>
      <Row gutter={[16, 16]}>
        {items.map(item => (
          <Col xs={24} sm={12} lg={12} xl={12} key={item.key}>
            <Card
              hoverable
              className="glass-card"
              style={{ cursor: 'pointer', height: '100%' }}
              onClick={() => navigate(item.key)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                {item.icon}
                <div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: '#e6edf3', marginBottom: 4 }}>
                    {item.title}
                  </div>
                  <Text type="secondary" style={{ fontSize: 13 }}>{item.desc}</Text>
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
