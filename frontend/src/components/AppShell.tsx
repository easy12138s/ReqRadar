import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Button, Dropdown, Avatar, Breadcrumb, theme, Badge, Popover, List, Typography } from 'antd';
import { useAuth } from '../context/AuthContext';
import { useThemeContext } from '../context/ThemeContext';
import { AnimatePresence } from 'framer-motion';
import PageTransition from './PageTransition';
import { useQuery } from '@tanstack/react-query';
import { getAnalyses } from '../api/analyses';
import type { AnalysisTask } from '../types/api';
import {
  DashboardOutlined,
  ProjectOutlined,
  ExperimentOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
  HomeOutlined,
  BulbOutlined,
  BellOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import PageLoader from './PageLoader';

const { Header, Content } = Layout;
const { Text } = Typography;

export default function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const { themeMode, toggleTheme } = useThemeContext();
  const { token } = theme.useToken();

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
    'mcp': 'MCP 设置',
      'profile': '项目画像',
      'synonyms': '同义词管理',
      'reports': '分析报告',
    };
    return map[segment] || segment;
  }

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

  // 轮询获取进行中的任务
  const { data: analyses = [] } = useQuery({
    queryKey: ['analyses-running'],
    queryFn: getAnalyses,
    refetchInterval: 5000, // 每5秒轮询一次
    enabled: isAuthenticated, // 只有登录后才轮询
  });

  const runningTasks = analyses.filter((t: AnalysisTask) => t.status === 'pending' || t.status === 'running');

  const notificationContent = (
    <div style={{ width: 300, maxHeight: 400, overflow: 'auto' }}>
      <div style={{ padding: '8px 0', borderBottom: `1px solid ${token.colorBorderSecondary}`, marginBottom: 8 }}>
        <Text strong>进行中的分析 ({runningTasks.length})</Text>
      </div>
      {runningTasks.length === 0 ? (
        <div style={{ padding: '24px 0', textAlign: 'center', color: token.colorTextSecondary }}>
          暂无进行中的任务
        </div>
      ) : (
        <List
          dataSource={runningTasks}
          renderItem={(item: AnalysisTask) => (
            <List.Item
              style={{ cursor: 'pointer', padding: '12px 8px', borderRadius: 8, transition: 'background 0.2s' }}
              onClick={() => navigate(`/analyses/${item.id}`)}
              className="notification-item"
            >
              <List.Item.Meta
                avatar={<LoadingOutlined style={{ color: token.colorPrimary }} />}
                title={<Text ellipsis style={{ width: 200 }}>{String(item.requirement_name || `分析 #${String(item.id).slice(0,8)}`)}</Text>}
                description={<Text type="secondary" style={{ fontSize: 12 }}>正在分析中...</Text>}
              />
            </List.Item>
          )}
        />
      )}
      <style>{`
        .notification-item:hover {
          background: rgba(0, 184, 212, 0.08);
        }
      `}</style>
    </div>
  );

  return (
    <Layout style={{ minHeight: '100vh', background: token.colorBgBase }}>
      <Header
        className="glass-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          height: 60,
          position: 'sticky',
          top: 0,
          zIndex: 100,
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

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Popover content={notificationContent} placement="bottomRight" trigger="click" arrow={false}>
            <Badge count={runningTasks.length} size="small" offset={[-4, 4]}>
              <Button 
                type="text" 
                icon={<BellOutlined />} 
                style={{ color: token.colorTextSecondary }}
              />
            </Badge>
          </Popover>
          <Button 
            type="text" 
            icon={<BulbOutlined />} 
            onClick={toggleTheme}
            style={{ color: token.colorTextSecondary }}
            title={themeMode === 'dark' ? '切换到亮色模式' : '切换到暗色模式'}
          />
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
        </div>
      </Header>

      <Content style={{ padding: '24px 32px', maxWidth: 1280, margin: '0 auto', width: '100%' }}>
        {pathParts.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <Breadcrumb
              className="breadcrumb-flat"
              items={breadcrumbItems.map(item => ({
                title: item.path === location.pathname ? item.title : (
                  <a onClick={() => navigate(item.path)} style={{ cursor: 'pointer' }}>
                    {item.title}
                  </a>
                ),
              }))}
            />
          </div>
        )}
        <AnimatePresence mode="wait">
          <PageTransition key={location.pathname}>
            <Outlet />
          </PageTransition>
        </AnimatePresence>
      </Content>
    </Layout>
  );
}
