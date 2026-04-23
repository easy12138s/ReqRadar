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
    label: '工作台',
  },
  {
    key: '/projects',
    icon: <ProjectOutlined />,
    label: '项目',
  },
  {
    key: '/analyses',
    icon: <FileSearchOutlined />,
    label: '分析',
  },
  {
    key: '/analyses/submit',
    icon: <HistoryOutlined />,
    label: '新建分析',
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