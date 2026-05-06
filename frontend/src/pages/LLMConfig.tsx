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
  { label: 'Ollama', value: 'ollama' },
];

interface LLMFormValues {
  provider: string;
  model: string;
  api_key: string;
  base_url: string;
  timeout: number;
  max_retries: number;
  embedding_model: string;
  embedding_dim: number;
  vision_provider: string;
  vision_model: string;
  vision_api_key: string;
  vision_base_url: string;
  vision_timeout: number;
}

const LLM_CONFIG_KEYS: Record<keyof LLMFormValues, string> = {
  provider: 'llm.provider',
  model: 'llm.model',
  api_key: 'llm.api_key',
  base_url: 'llm.base_url',
  timeout: 'llm.timeout',
  max_retries: 'llm.max_retries',
  embedding_model: 'llm.embedding_model',
  embedding_dim: 'llm.embedding_dim',
  vision_provider: 'vision.provider',
  vision_model: 'vision.model',
  vision_api_key: 'vision.api_key',
  vision_base_url: 'vision.base_url',
  vision_timeout: 'vision.timeout',
};

const DEFAULT_VALUES: LLMFormValues = {
  provider: 'openai',
  model: 'gpt-4o-mini',
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  timeout: 60,
  max_retries: 2,
  embedding_model: 'text-embedding-3-small',
  embedding_dim: 1024,
  vision_provider: 'openai',
  vision_model: 'gpt-4o',
  vision_api_key: '',
  vision_base_url: 'https://api.openai.com/v1',
  vision_timeout: 120,
};

export function LLMConfig() {
  const [form] = Form.useForm<LLMFormValues>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  const [apiKeyHidden, setApiKeyHidden] = useState(true);
  const [visionApiKeyHidden, setVisionApiKeyHidden] = useState(true);

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
        if (value !== undefined && value !== '') {
          const valueType = typeof value === 'number' ? 'int' : typeof value === 'boolean' ? 'bool' : 'str';
          await setUserConfig(key, {
            value,
            value_type: valueType,
            is_sensitive: key.includes('api_key'),
          });
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

  const handleReset = () => {
    form.setFieldsValue(DEFAULT_VALUES);
    message.info('已重置为默认值，请点击保存');
  };

  const provider = Form.useWatch('provider', form);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>大模型配置</Title>
        <Button
          size="small"
          loading={testLoading}
          onClick={async () => {
            setTestLoading(true);
            try {
              const resp = await fetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } });
              if (resp.ok) {
                message.success('API 连接正常');
              } else {
                message.error(`连接失败: ${resp.status}`);
              }
            } catch {
              message.error('无法连接到服务器');
            } finally {
              setTestLoading(false);
            }
          }}
        >
          测试连接
        </Button>
      </div>
      <Alert
        message="提示"
        description="此处配置的用户级配置优先级高于系统配置文件 (.reqradar.yaml)。API Key 等敏感信息将以掩码形式显示。"
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        initialValues={DEFAULT_VALUES}
        disabled={loading}
      >
        <Card title="文本分析模型" style={{ marginBottom: 16 }}>
          <Form.Item
            label="LLM 提供商"
            name="provider"
            rules={[{ required: true, message: '请选择提供商' }]}
          >
            <Select options={LLM_PROVIDERS} />
          </Form.Item>

          <Form.Item
            label="模型名称"
            name="model"
            rules={[{ required: true, message: '请输入模型名称' }]}
          >
            <Input placeholder="例如: gpt-4o-mini" />
          </Form.Item>

          <Form.Item
            label="API Key"
            name="api_key"
            tooltip="敏感信息，保存后以掩码形式显示"
          >
            <Input.Password
              placeholder="sk-..."
              visibilityToggle={{ visible: !apiKeyHidden, onVisibleChange: (v) => setApiKeyHidden(!v) }}
            />
          </Form.Item>

          <Form.Item
            label="Base URL"
            name="base_url"
            tooltip="OpenAI 兼容的 API 地址"
          >
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>

          <Space size={16}>
            <Form.Item label="超时时间 (秒)" name="timeout">
              <InputNumber min={1} max={300} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item label="最大重试次数" name="max_retries">
              <InputNumber min={0} max={10} style={{ width: 120 }} />
            </Form.Item>
          </Space>
        </Card>

        <Card title="嵌入模型" style={{ marginBottom: 16 }}>
          <Form.Item label="嵌入模型名称" name="embedding_model">
            <Input placeholder="例如: text-embedding-3-small" />
          </Form.Item>
          <Form.Item label="向量维度" name="embedding_dim">
            <InputNumber min={64} max={4096} style={{ width: 160 }} />
          </Form.Item>
        </Card>

        <Card title="视觉分析模型" style={{ marginBottom: 16 }}>
          <Form.Item
            label="视觉 LLM 提供商"
            name="vision_provider"
          >
            <Select options={LLM_PROVIDERS} />
          </Form.Item>

          <Form.Item
            label="视觉模型名称"
            name="vision_model"
          >
            <Input placeholder="例如: gpt-4o" />
          </Form.Item>

          <Form.Item
            label="API Key"
            name="vision_api_key"
            tooltip="可与文本分析模型共用"
          >
            <Input.Password
              placeholder="sk-..."
              visibilityToggle={{ visible: !visionApiKeyHidden, onVisibleChange: (v) => setVisionApiKeyHidden(!v) }}
            />
          </Form.Item>

          <Form.Item
            label="Base URL"
            name="vision_base_url"
          >
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>

          <Form.Item label="超时时间 (秒)" name="vision_timeout">
            <InputNumber min={1} max={300} style={{ width: 120 }} />
          </Form.Item>
        </Card>

        {provider === 'ollama' && (
          <Alert
            message="Ollama 模式"
            description="使用 Ollama 时，API Key 和 Base URL 将被忽略。请确保本地 Ollama 服务已启动并加载了指定模型。"
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={saving}>
              保存配置
            </Button>
            <Button icon={<ReloadOutlined />} onClick={handleReset}>
              重置为默认
            </Button>
            <Button onClick={loadConfigs}>
              重新加载
            </Button>
          </Space>
        </Form.Item>
      </Form>

      <Divider />
      <Card title="配置优先级说明" size="small">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>配置值按以下优先级从高到低解析：</Text>
          <Space>
            <Tag color="red">1. 用户级配置</Tag>
            <Text type="secondary">（即本页面设置的值）</Text>
          </Space>
          <Space>
            <Tag color="orange">2. 项目级配置</Tag>
            <Text type="secondary">（项目设置页面）</Text>
          </Space>
          <Space>
            <Tag color="blue">3. 系统级配置</Tag>
            <Text type="secondary">（管理员设置）</Text>
          </Space>
          <Space>
            <Tag>4. 配置文件</Tag>
            <Text type="secondary">（.reqradar.yaml）</Text>
          </Space>
          <Space>
            <Tag color="default">5. 默认值</Tag>
            <Text type="secondary">（代码内置默认值）</Text>
          </Space>
        </Space>
      </Card>
    </div>
  );
}
