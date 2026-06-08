import { useState, useEffect } from 'react';
import {
  Card, Table, Button, Typography, Modal, Select, message, Space, Popconfirm, Form, Input, theme,
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
  const [form] = Form.useForm();
  const { token } = theme.useToken();

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

  const handleCreate = async (values: any) => {
    setAdding(true);
    try {
      await register({
        email: values.email,
        password: values.password,
        display_name: values.display_name,
      });
      message.success(`用户 ${values.email} 创建成功`);
      setAddOpen(false);
      form.resetFields();
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
      render: (v: string) => <span style={{ color: token.colorText }}>{v}</span>,
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
        <Title level={4} style={{ margin: 0, color: token.colorTextHeading }}>用户管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadUsers}>刷新</Button>
          <Button type="primary" icon={<UserAddOutlined />} onClick={() => setAddOpen(true)}>
            添加用户
          </Button>
        </Space>
      </div>

      <Card className="flat-card">
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
        onCancel={() => { setAddOpen(false); form.resetFields(); }}
        onOk={() => form.submit()}
        confirmLoading={adding}
        okText="确认添加"
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            label="邮箱"
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '邮箱格式不正确' },
            ]}
          >
            <Input placeholder="请输入邮箱" />
          </Form.Item>
          <Form.Item
            label="显示名称"
            name="display_name"
            rules={[{ required: true, message: '请输入显示名称' }]}
          >
            <Input placeholder="请输入显示名称" />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 8, message: '密码至少8位' },
              { pattern: /[A-Z]/, message: '需要大写字母' },
              { pattern: /[a-z]/, message: '需要小写字母' },
              { pattern: /[0-9]/, message: '需要数字' },
            ]}
          >
            <Input.Password placeholder="设置密码" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
