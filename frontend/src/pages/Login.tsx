import { useState } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Typography,
  message,
} from 'antd';
import { LoginOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { login } from '@/api/auth';

const { Title } = Typography;

export function Login() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login: authLogin } = useAuth();

  const handleLogin = async (values: { email: string; password: string }) => {
    setLoading(true);
    try {
      const response = await login(values);
      authLogin(response.access_token);
      message.success('登录成功');
      navigate('/');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string; message?: string } }; message?: string };
      message.error(err.response?.data?.detail || err.response?.data?.message || err.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#0a0e17',
      }}
    >
      <Card
        className="glass-card"
        style={{ width: 400 }}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <img src="/logo.svg" alt="ReqRadar" style={{ width: 48, height: 48, margin: '0 auto 16px' }} />
          <Title level={3} style={{ margin: 0, color: '#f0f6fc' }}>
            ReqRadar
          </Title>
          <Typography.Text type="secondary">
            需求透视分析平台
          </Typography.Text>
        </div>
        <Form
          name="login"
          onFinish={handleLogin}
          autoComplete="off"
          layout="vertical"
        >
          <Form.Item
            label="邮箱"
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input placeholder="请输入邮箱" />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password placeholder="请输入密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              <LoginOutlined /> 登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
