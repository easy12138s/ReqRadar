import { Menu } from 'antd';
import {
  DashboardOutlined,
  ProjectOutlined,
  FileSearchOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

interface NavMenuProps {
  collapsed?: boolean;
}

const items = [
  {
    key: '/',
    icon: <DashboardOutlined />,
    label: 'Dashboard',
  },
  {
    key: '/projects',
    icon: <ProjectOutlined />,
    label: 'Projects',
  },
  {
    key: '/analyses',
    icon: <FileSearchOutlined />,
    label: 'Analyses',
  },
  {
    key: '/analyses/submit',
    icon: <HistoryOutlined />,
    label: 'New Analysis',
  },
];

export function NavMenu({ collapsed }: NavMenuProps) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Menu
      mode="inline"
      selectedKeys={[location.pathname]}
      items={items}
      onClick={({ key }) => navigate(key)}
      style={{ borderRight: 0 }}
      inlineCollapsed={collapsed}
    />
  );
}
