import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Button, Dropdown, Avatar, theme } from 'antd';
import { useAuth } from '../context/AuthContext';
import {
  DashboardOutlined,
  ProjectOutlined,
  ExperimentOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons';
import PageLoader from './PageLoader';

const { Header, Content } = Layout;

const navItems = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/projects', icon: <ProjectOutlined />, label: '项目' },
  { key: '/analyses', icon: <ExperimentOutlined />, label: '分析' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
];

export default function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const { token } = theme.useToken();

  if (isLoading) {
    return <PageLoader />;
  }

  if (!isAuthenticated) {
    navigate('/login', { replace: true });
    return <PageLoader />;
  }

  const currentKey = navItems.find(item =>
    item.key === '/'
      ? location.pathname === '/'
      : location.pathname.startsWith(item.key)
  )?.key || '/';

  const userMenu = {
    items: [
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
        danger: true,
      },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === 'logout') logout();
    },
  };

  return (
    <Layout style={{ minHeight: '100vh', background: token.colorBgBase }}>
      <Header
        className="glass"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          height: 56,
          position: 'sticky',
          top: 0,
          zIndex: 100,
          borderBottom: `1px solid ${token.colorBorder}`,
          background: 'rgba(15,22,36,0.85)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}
            onClick={() => navigate('/')}
          >
            <div style={{
              width: 28, height: 28,
              background: 'linear-gradient(135deg, #00d4ff, #7c3aed)',
              borderRadius: 7,
            }} />
            <span style={{ fontWeight: 700, fontSize: 16, color: '#f0f6fc', letterSpacing: -0.3 }}>
              ReqRadar
            </span>
          </div>

          <nav style={{ display: 'flex', gap: 4 }}>
            {navItems.map(item => (
              <Button
                key={item.key}
                type="text"
                icon={item.icon}
                onClick={() => navigate(item.key)}
                style={{
                  color: currentKey === item.key ? token.colorPrimary : token.colorTextSecondary,
                  fontWeight: currentKey === item.key ? 600 : 400,
                  background: currentKey === item.key ? `${token.colorPrimary}15` : 'transparent',
                  borderRadius: 8,
                  height: 36,
                }}
              >
                {item.label}
              </Button>
            ))}
          </nav>
        </div>

        <Dropdown menu={userMenu} placement="bottomRight">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
            <span style={{ fontSize: 13, color: token.colorTextSecondary, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.email || ''}
            </span>
            <Avatar
              size={32}
              icon={<UserOutlined />}
              style={{ background: 'linear-gradient(135deg, #00d4ff, #7c3aed)' }}
            />
          </div>
        </Dropdown>
      </Header>

      <Content style={{ padding: 24, maxWidth: 1280, margin: '0 auto', width: '100%' }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
