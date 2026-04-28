import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { FileTextOutlined, SettingOutlined, ApiOutlined } from '@ant-design/icons';

const { Sider, Content } = Layout;

export function SettingsLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { key: '/settings/llm', icon: <ApiOutlined />, label: '大模型配置' },
    { key: '/settings/templates', icon: <FileTextOutlined />, label: '报告模板' },
    { key: '/settings/preferences', icon: <SettingOutlined />, label: '用户偏好' },
  ];

  return (
    <Layout style={{ minHeight: '100%', background: '#fff' }}>
      <Sider width={200} style={{ background: '#fff' }}>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Content style={{ padding: 24 }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
