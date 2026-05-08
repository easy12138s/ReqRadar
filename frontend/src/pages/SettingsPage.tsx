import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, Typography, theme } from 'antd';
import { useTranslation } from 'react-i18next';
import {
  RobotOutlined, FileTextOutlined, UserOutlined, TeamOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;

export default function SettingsPage() {
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const { t } = useTranslation();

  const items = [
    { key: '/settings/llm', icon: <RobotOutlined style={{ fontSize: 32, color: token.colorInfo }} />, title: t('settings.llm'), desc: t('settings.llmDesc') },
    { key: '/settings/templates', icon: <FileTextOutlined style={{ fontSize: 32, color: token.colorPrimary }} />, title: t('settings.templates'), desc: t('settings.templatesDesc') },
    { key: '/settings/preferences', icon: <UserOutlined style={{ fontSize: 32, color: token.colorSuccess }} />, title: t('settings.preferences'), desc: t('settings.preferencesDesc') },
    { key: '/settings/users', icon: <TeamOutlined style={{ fontSize: 32, color: token.colorWarning }} />, title: t('settings.users'), desc: t('settings.usersDesc') },
  ];

  return (
    <div>
      <Title level={4}>{t('settings.title')}</Title>
      <Row gutter={[16, 16]}>
        {items.map(item => (
          <Col xs={24} sm={12} lg={12} xl={12} key={item.key}>
            <Card
              hoverable
              style={{ background: token.colorBgContainer, border: '1px solid #1e293b', cursor: 'pointer', height: '100%' }}
              onClick={() => navigate(item.key)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                {item.icon}
                <div>
                  <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
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
