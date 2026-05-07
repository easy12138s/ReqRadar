import { useState, useEffect } from 'react';
import {
  Card, Table, Button, Typography, Modal, Select, message, Space, Popconfirm,
} from 'antd';
import { UserAddOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { getUsers, updateUser, deleteUser, type UserInfo } from '../api/users';
import { register } from '../api/auth';
import PageLoader from '../components/PageLoader';

const { Title } = Typography;

export default function UserManagement() {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');

  const loadUsers = async () => {
    setLoading(true);
    try {
      const data = await getUsers();
      setUsers(data);
    } catch {
      message.error('加载用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadUsers(); }, []);

  const handleAdd = async () => {
    if (!email || !displayName) {
      message.warning('请填写邮箱和显示名称');
      return;
    }
    setAdding(true);
    try {
      await register({ email, display_name: displayName, password: 'User12138%' });
      message.success(`用户 ${email} 创建成功，默认密码: User12138%`);
      setAddOpen(false);
      setEmail('');
      setDisplayName('');
      loadUsers();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '创建失败');
    } finally {
      setAdding(false);
    }
  };

  const handleRoleChange = async (userId: number, role: string) => {
    try {
      await updateUser(userId, { role });
      message.success('角色已更新');
      loadUsers();
    } catch {
      message.error('更新失败');
    }
  };

  const handleDelete = async (userId: number) => {
    try {
      await deleteUser(userId);
      message.success('用户已删除');
      loadUsers();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败');
    }
  };

  if (loading) return <PageLoader />;

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 60,
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      render: (v: string) => <span style={{ color: '#e2e8f0' }}>{v}</span>,
    },
    {
      title: '显示名称',
      dataIndex: 'display_name',
    },
    {
      title: '角色',
      dataIndex: 'role',
      render: (role: string, record: UserInfo) => (
        <Select
          value={role}
          size="small"
          style={{ width: 100 }}
          options={[
            { label: 'Admin', value: 'admin' },
            { label: 'User', value: 'user' },
          ]}
          onChange={(v) => handleRoleChange(record.id, v)}
        />
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '',
    },
    {
      title: '操作',
      width: 80,
      render: (_: unknown, record: UserInfo) => (
        <Popconfirm
          title="确定删除此用户？"
          onConfirm={() => handleDelete(record.id)}
          okText="删除"
          cancelText="取消"
        >
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, color: '#f7fafc' }}>用户管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadUsers}>刷新</Button>
          <Button type="primary" icon={<UserAddOutlined />} onClick={() => setAddOpen(true)}>
            添加用户
          </Button>
        </Space>
      </div>

      <Card className="glass-card">
        <Table
          dataSource={users}
          columns={columns}
          rowKey="id"
          pagination={false}
          size="middle"
        />
      </Card>

      <Modal
        title="添加用户"
        open={addOpen}
        onCancel={() => { setAddOpen(false); setEmail(''); setDisplayName(''); }}
        onOk={handleAdd}
        confirmLoading={adding}
        okText="确认添加"
      >
        <div style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 4, color: '#a0aec0', fontSize: 13 }}>邮箱</div>
          <input
            type="email"
            placeholder="请输入邮箱"
            value={email}
            onChange={e => setEmail(e.target.value)}
            style={{
              width: '100%', padding: '8px 12px', borderRadius: 6,
              background: '#1f2937', border: '1px solid #2d3748', color: '#e2e8f0', fontSize: 14, outline: 'none',
            }}
          />
        </div>
        <div style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 4, color: '#a0aec0', fontSize: 13 }}>显示名称</div>
          <input
            placeholder="请输入显示名称"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
            style={{
              width: '100%', padding: '8px 12px', borderRadius: 6,
              background: '#1f2937', border: '1px solid #2d3748', color: '#e2e8f0', fontSize: 14, outline: 'none',
            }}
          />
        </div>
        <div style={{ padding: '8px 12px', background: 'rgba(0,212,255,0.08)', borderRadius: 6, fontSize: 13, color: '#00d4ff' }}>
          默认密码: <strong>User12138%</strong>
        </div>
      </Modal>
    </div>
  );
}
