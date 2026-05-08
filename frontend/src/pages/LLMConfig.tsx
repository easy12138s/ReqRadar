import { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  Typography,
  message,
  Divider,
  Space,
  Alert,
  Tag,
  InputNumber,
} from 'antd';
import { SaveOutlined, ReloadOutlined } from '@ant-design/icons';
import { setUserConfig, getUserConfig } from '@/api/configs';

const { Title, Text } = Typography;

const LLM_PROVIDERS = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic (Claude)', value: 'anthropic' },
  { label: 'Google Gemini', value: 'gemini' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'Ollama', value: 'ollama' },
  { label: 'OpenAI 兼容', value: 'openai' },
];

interface LLMFormValues {
  provider: string;
  model: string;
  api_key: string;
  base_url: string;
  host: string;
  timeout: number;
  max_retries: number;
}

const LLM_CONFIG_KEYS: Record<keyof LLMFormValues, string> = {
  provider: 'llm.provider',
  model: 'llm.model',
  api_key: 'llm.api_key',
  base_url: 'llm.base_url',
  host: 'llm.host',
  timeout: 'llm.timeout',
  max_retries: 'llm.max_retries',
};

const DEFAULT_VALUES: LLMFormValues = {
  provider: 'openai',
  model: 'gpt-4o-mini',
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  host: 'http://localhost:11434',
  timeout: 60,
  max_retries: 2,
};

export function LLMConfig() {
  const [form] = Form.useForm<LLMFormValues>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [apiKeyHidden, setApiKeyHidden] = useState(true);

  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    setLoading(true);
    try {
      const values: Partial<LLMFormValues> = {};
      const promises = Object.entries(LLM_CONFIG_KEYS).map(async ([field, key]) => {
        try {
          const res = await getUserConfig(key);
          return { field, value: res.value };
        } catch {
          return { field, value: undefined };
        }
      });
      const results = await Promise.all(promises);
      results.forEach(({ field, value }) => {
        if (value !== undefined) {
          (values as Record<string, unknown>)[field] = value;
        }
      });
      form.setFieldsValue({ ...DEFAULT_VALUES, ...values });
    } catch {
      message.error('加载配置失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (values: LLMFormValues) => {
    setSaving(true);
    try {
      const promises = Object.entries(LLM_CONFIG_KEYS).map(async ([field, key]) => {
        const value = values[field as keyof LLMFormValues];
        if (value !== undefined) {
          const valueType = typeof value === 'number' ? 'int' : typeof value === 'boolean' ? 'bool' : 'str';
          await setUserConfig(key, { value: String(value), value_type: valueType, is_sensitive: key.includes('api_key') });
        }
      });
      await Promise.all(promises);
      message.success('配置已保存');
    } catch {
      message.error('保存配置失败');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTestLoading(true);
    try {
      const values = form.getFieldsValue();
      const token = localStorage.getItem('access_token');
      const resp = await fetch('/api/me/test-llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          provider: values.provider || 'openai',
          api_key: values.api_key || '',
          base_url: values.base_url || 'https://api.openai.com/v1',
          model: values.model || 'gpt-4o-mini',
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        message.success(data.message || '连接成功');
      } else {
        const err = await resp.json();
        message.error(err.detail || '连接失败');
      }
    } catch {
      message.error('无法连接到服务器');
    } finally {
      setTestLoading(false);
    }
  };

  const handleReset = () => {
    form.setFieldsValue(DEFAULT_VALUES);
    message.info('已重置为默认值，请点击保存');
  };

  const provider = Form.useWatch('provider', form);

  return (
    <div>
      <Title level={3}>大模型配置</Title>

      <Alert
        message="用户级配置优先级高于系统配置文件 (.reqradar.yaml)，API Key 等敏感信息保存后以掩码形式显示。"
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
      />

      <Space style={{ marginBottom: 24 }}>
        <Button onClick={handleTest} loading={testLoading}>
          测试连接
        </Button>
        <Button type="primary" icon={<SaveOutlined />} onClick={() => form.submit()} loading={saving}>
          保存配置
        </Button>
        <Button icon={<ReloadOutlined />} onClick={handleReset}>
          重置为默认
        </Button>
        <Button onClick={loadConfigs}>
           重新加载
        </Button>
        <Button
          danger
          onClick={async () => {
            const promises = Object.values(LLM_CONFIG_KEYS).map(async (key) => {
              await setUserConfig(key, { value: '', value_type: 'str', is_sensitive: key.includes('api_key') });
            });
            await Promise.all(promises);
            form.setFieldsValue(DEFAULT_VALUES);
            message.success('配置已清除');
          }}
        >
           清除配置
        </Button>
      </Space>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={DEFAULT_VALUES}
        disabled={loading}
      >
        <Card title="文本分析模型" style={{ marginBottom: 16 }}>
          <Form.Item label="LLM 提供商" name="provider" rules={[{ required: true, message: '请选择提供商' }]}>
            <Select options={LLM_PROVIDERS} />
          </Form.Item>
          <Form.Item label="模型名称" name="model" rules={[{ required: true, message: '请输入模型名称' }]}>
            <Input placeholder="例如: gpt-4o-mini" />
          </Form.Item>
          <Form.Item label="API Key" name="api_key" tooltip="敏感信息，保存后以掩码形式显示">
            <Input.Password
              placeholder="sk-..."
              visibilityToggle={{ visible: !apiKeyHidden, onVisibleChange: (v) => setApiKeyHidden(!v) }}
            />
          </Form.Item>
          <Form.Item label="Base URL" name="base_url" tooltip="OpenAI 兼容的 API 地址">
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          {provider === 'ollama' && (
            <Form.Item label="Ollama Host" name="host" tooltip="Ollama 服务地址">
              <Input placeholder="http://localhost:11434" />
            </Form.Item>
          )}
          <Space size={16}>
            <Form.Item label="超时 (秒)" name="timeout">
              <InputNumber min={1} max={300} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item label="最大重试" name="max_retries">
              <InputNumber min={0} max={10} style={{ width: 120 }} />
            </Form.Item>
          </Space>
        </Card>

        {provider === 'ollama' && (
          <Alert
            message="Ollama 模式"
            description="Ollama v0.5+ 已支持 OpenAI 兼容 API (http://localhost:11434/v1)。请确保本地 Ollama 服务已启动并加载了指定模型。"
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}
      </Form>

      <Divider />
      <Card title="配置优先级说明" size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space><Tag color="red">1. 用户级配置</Tag><Text type="secondary">（本页面）</Text></Space>
          <Space><Tag color="orange">2. 项目级配置</Tag><Text type="secondary">（项目设置）</Text></Space>
          <Space><Tag color="blue">3. 系统级配置</Tag><Text type="secondary">（管理员设置）</Text></Space>
          <Space><Tag>4. 配置文件</Tag><Text type="secondary">（.reqradar.yaml）</Text></Space>
          <Space><Tag color="default">5. 默认值</Tag><Text type="secondary">（代码默认值）</Text></Space>
        </Space>
      </Card>
    </div>
  );
}
