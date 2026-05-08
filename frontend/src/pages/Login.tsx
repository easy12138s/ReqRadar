import { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Typography,
  message,
} from 'antd';
import { useTranslation } from 'react-i18next';
import { LoginOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { login } from '@/api/auth';

const { Title } = Typography;

const TAGLINE = 'AI 驱动的需求透视分析平台';

export function Login() {
  const [loading, setLoading] = useState(false);
  const [displayedTagline, setDisplayedTagline] = useState('');
  const navigate = useNavigate();
  const { login: authLogin } = useAuth();
  const { t } = useTranslation();

  useEffect(() => {
    let i = 0;
    const interval = setInterval(() => {
      if (i < TAGLINE.length) {
        setDisplayedTagline(TAGLINE.slice(0, i + 1));
        i++;
      } else {
        clearInterval(interval);
      }
    }, 80);
    return () => clearInterval(interval);
  }, []);

  const handleLogin = async (values: { email: string; password: string }) => {
    setLoading(true);
    try {
      const response = await login(values);
      authLogin(response.access_token);
      message.success(t('login.success'));
      navigate('/');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string; message?: string } }; message?: string };
      message.error(err.response?.data?.detail || err.response?.data?.message || err.message || t('login.failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-bg" style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <Card className="login-card" style={{ width: 420, padding: '8px 8px 0' }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <img
            src="/app/logo.svg"
            alt="ReqRadar"
            style={{ width: 64, height: 64, margin: '0 auto 20px', display: 'block', filter: 'drop-shadow(0 0 12px rgba(0,212,255,0.3))' }}
          />
          <Title level={2} style={{ margin: '0 0 8px', color: '#f0f6fc', letterSpacing: 2 }}>
            ReqRadar
          </Title>
          <Typography.Text
            style={{
              color: '#00d4ff',
              fontSize: 14,
              fontWeight: 500,
              minHeight: 20,
              display: 'inline-block',
            }}
          >
            {displayedTagline}
            <span className="typing-cursor" />
          </Typography.Text>
        </div>
        <Form
          name="login"
          onFinish={handleLogin}
          autoComplete="off"
          layout="vertical"
          size="large"
        >
          <Form.Item
            label={<span style={{ color: '#94a3b8' }}>{t('login.email')}</span>}
            name="email"
            rules={[
              { required: true, message: t('login.emailRequired') },
              { type: 'email', message: t('login.emailInvalid') },
            ]}
          >
            <Input placeholder={t('login.emailPlaceholder')} />
          </Form.Item>
          <Form.Item
            label={<span style={{ color: '#94a3b8' }}>{t('login.password')}</span>}
            name="password"
            rules={[{ required: true, message: t('login.passwordRequired') }]}
          >
            <Input.Password placeholder={t('login.passwordPlaceholder')} />
          </Form.Item>
          <Form.Item style={{ marginBottom: 12 }}>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">
              <LoginOutlined /> {t('login.submit')}
            </Button>
          </Form.Item>
        </Form>
        <div style={{ textAlign: 'center', paddingBottom: 16 }}>
          <Typography.Text style={{ color: '#475569', fontSize: 12 }}>
            ReqRadar v0.8.0
          </Typography.Text>
        </div>
      </Card>
    </div>
  );
}
