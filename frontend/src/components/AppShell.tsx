import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Button, Dropdown, Avatar, Breadcrumb, theme } from 'antd';
import { useAuth } from '../context/AuthContext';
import {
  DashboardOutlined,
  ProjectOutlined,
  ExperimentOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
  HomeOutlined,
} from '@ant-design/icons';
import PageLoader from './PageLoader';

const { Header, Content } = Layout;

const navItems = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/projects', icon: <ProjectOutlined />, label: '项目' },
  { key: '/analyses', icon: <ExperimentOutlined />, label: '分析' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
];

function getBreadcrumbTitle(segment: string): string {
  const map: Record<string, string> = {
    'projects': '项目',
    'analyses': '分析',
    'settings': '设置',
    'llm': 'LLM 配置',
    'templates': '报告模板',
    'preferences': '偏好设置',
    'users': '用户管理',
    'profile': '项目画像',
    'synonyms': '同义词管理',
    'reports': '分析报告',
  };
  return map[segment] || segment;
}

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

  const pathParts = location.pathname.split('/').filter(Boolean);
  const breadcrumbItems = [
    { title: <HomeOutlined />, path: '/' },
    ...pathParts.map((part, i) => ({
      title: getBreadcrumbTitle(part),
      path: '/' + pathParts.slice(0, i + 1).join('/'),
    })),
  ];

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
        className="flat-header"
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
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 32 }}>
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}
            onClick={() => navigate('/')}
          >
            <img src="/app/logo.svg" alt="ReqRadar" style={{ width: 28, height: 28 }} />
            <span style={{ fontWeight: 700, fontSize: 16, color: token.colorText, letterSpacing: -0.3 }}>
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
              style={{ background: token.colorPrimary }}
            />
          </div>
        </Dropdown>
      </Header>

      <Content style={{ padding: 24, maxWidth: 1280, margin: '0 auto', width: '100%' }}>
        {pathParts.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <Breadcrumb
              className="breadcrumb-flat"
              items={breadcrumbItems.map(item => ({
                title: item.path === location.pathname ? item.title : (
                  <a onClick={() => navigate(item.path)} style={{ color: '#64748b', cursor: 'pointer' }}>
                    {item.title}
                  </a>
                ),
              }))}
            />
          </div>
        )}
        <Outlet />
      </Content>
    </Layout>
  );
}
