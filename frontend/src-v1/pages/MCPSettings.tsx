import { useState, useEffect } from 'react';
import {
  Card,
  Form,
  Input,
  InputNumber,
  Switch,
  Button,
  Typography,
  Table,
  Space,
  Modal,
  Popconfirm,
  message,
  Tag,
  theme,
} from 'antd';
import { SaveOutlined, ReloadOutlined, PlusOutlined, DeleteOutlined, CopyOutlined } from '@ant-design/icons';
import {
  getMCPConfig,
  updateMCPConfig,
  listMCPKeys,
  createMCPKey,
  revokeMCPKey,
  reExportMCPKey,
  listMCPToolCalls,
  cleanupMCPAudit,
  type MCPConfigData,
  type MCPAccessKey,
  type MCPCreateKeyResult,
  type MCPToolCall,
} from '@/api/mcp';

const { Title, Text } = Typography;

export function MCPSettings() {
  const [form] = Form.useForm<MCPConfigData>();
  const [configLoading, setConfigLoading] = useState(true);
  const [configSaving, setConfigSaving] = useState(false);
  const [keys, setKeys] = useState<MCPAccessKey[]>([]);
  const [keysLoading, setKeysLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [creatingKey, setCreatingKey] = useState(false);
  const [createdResult, setCreatedResult] = useState<MCPCreateKeyResult | null>(null);
  const [resultModalOpen, setResultModalOpen] = useState(false);
  const [auditLogs, setAuditLogs] = useState<MCPToolCall[]>([]);
  const [auditLoading, setAuditLoading] = useState(true);
  const [auditOffset, setAuditOffset] = useState(0);
  const [auditLimit] = useState(20);
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const { token } = theme.useToken();

  useEffect(() => {
    loadConfig();
    loadKeys();
    loadAuditLogs();
  }, []);

  const loadConfig = async () => {
    setConfigLoading(true);
    try {
      const data = await getMCPConfig();
      form.setFieldsValue(data);
    } catch {
      message.error('加载 MCP 配置失败');
    } finally {
      setConfigLoading(false);
    }
  };

  const handleSave = async (values: MCPConfigData) => {
    setConfigSaving(true);
    try {
      await updateMCPConfig(values);
      message.success('配置已保存');
    } catch {
      message.error('保存配置失败');
    } finally {
      setConfigSaving(false);
    }
  };

  const loadKeys = async () => {
    setKeysLoading(true);
    try {
      const data = await listMCPKeys();
      setKeys(data);
    } catch {
      message.error('加载访问密钥失败');
    } finally {
      setKeysLoading(false);
    }
  };

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      message.warning('请输入密钥名称');
      return;
    }
    setCreatingKey(true);
    try {
      const result = await createMCPKey(newKeyName.trim());
      setCreatedResult(result);
      setResultModalOpen(true);
      setCreateModalOpen(false);
      setNewKeyName('');
      loadKeys();
    } catch {
      message.error('创建密钥失败');
    } finally {
      setCreatingKey(false);
    }
  };

  const handleRevoke = async (keyId: number) => {
    try {
      await revokeMCPKey(keyId);
      message.success('密钥已撤销');
      loadKeys();
    } catch {
      message.error('撤销密钥失败');
    }
  };

  const handleReExport = async (keyId: number) => {
    try {
      const result = await reExportMCPKey(keyId);
      message.success(`重新导出成功: ${result.url}`);
    } catch {
      message.error('重新导出失败');
    }
  };

  const handleCopyConfig = () => {
    if (createdResult) {
      navigator.clipboard.writeText(JSON.stringify(createdResult.mcp_config, null, 2)).then(() => {
        message.success('已复制到剪贴板');
      }).catch(() => {
        message.error('复制失败');
      });
    }
  };

  const loadAuditLogs = async (offset = 0) => {
    setAuditLoading(true);
    try {
      const data = await listMCPToolCalls({ limit: auditLimit, offset });
      setAuditLogs(data);
      setAuditOffset(offset);
    } catch {
      message.error('加载审计日志失败');
    } finally {
      setAuditLoading(false);
    }
  };

  const handleCleanup = async () => {
    setCleanupLoading(true);
    try {
      const result = await cleanupMCPAudit();
      message.success(`已清理 ${result.deleted} 条记录`);
      loadAuditLogs(0);
    } catch {
      message.error('清理审计日志失败');
    } finally {
      setCleanupLoading(false);
    }
  };

  const keyColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '前缀', dataIndex: 'key_prefix', key: 'key_prefix' },
    {
      title: '权限',
      dataIndex: 'scopes',
      key: 'scopes',
      render: (scopes: string[]) => scopes.map((s) => <Tag key={s}>{s}</Tag>),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) =>
        active ? <Tag color="green">活跃</Tag> : <Tag color="red">已撤销</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string | null) => v || '-',
    },
    {
      title: '最后使用',
      dataIndex: 'last_used_at',
      key: 'last_used_at',
      render: (v: string | null) => v || '-',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: MCPAccessKey) => (
        <Space>
          {record.is_active && (
            <Popconfirm title="确定撤销此密钥？" onConfirm={() => handleRevoke(record.id)}>
              <Button size="small" danger icon={<DeleteOutlined />}>
                撤销
              </Button>
            </Popconfirm>
          )}
          <Button size="small" onClick={() => handleReExport(record.id)}>
            重新导出
          </Button>
        </Space>
      ),
    },
  ];

  const auditColumns = [
    { title: '工具名称', dataIndex: 'tool_name', key: 'tool_name' },
    { title: '密钥 ID', dataIndex: 'access_key_id', key: 'access_key_id', render: (v: number | null) => v ?? '-' },
    {
      title: '耗时 (ms)',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
    },
    {
      title: '状态',
      dataIndex: 'success',
      key: 'success',
      render: (success: boolean) =>
        success ? <Tag color="green">成功</Tag> : <Tag color="red">失败</Tag>,
    },
    {
      title: '结果摘要',
      dataIndex: 'result_summary',
      key: 'result_summary',
      ellipsis: true,
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string | null) => v || '-',
    },
  ];

  return (
    <div>
      <Title level={3}>MCP 设置</Title>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSave}
        disabled={configLoading}
      >
        <Card
          title="MCP 服务配置"
          style={{ background: token.colorBgContainer, border: '1px solid #1e293b' }}
        >
          <Space size={16} style={{ marginBottom: 16 }}>
            <Form.Item label="启用 MCP" name="enabled" valuePropName="checked" style={{ marginBottom: 0 }}>
              <Switch />
            </Form.Item>
            <Form.Item label="随 Web 服务启动" name="auto_start_with_web" valuePropName="checked" style={{ marginBottom: 0 }}>
              <Switch />
            </Form.Item>
            <Form.Item label="审计日志" name="audit_enabled" valuePropName="checked" style={{ marginBottom: 0 }}>
              <Switch />
            </Form.Item>
          </Space>
          <Space size={16}>
            <Form.Item label="Host" name="host">
              <Input placeholder="0.0.0.0" />
            </Form.Item>
            <Form.Item label="Port" name="port">
              <InputNumber min={1} max={65535} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item label="Path" name="path">
              <Input placeholder="/mcp" />
            </Form.Item>
          </Space>
          <Form.Item label="Public URL" name="public_url" tooltip="可选，用于生成外部访问地址">
            <Input placeholder="https://example.com/mcp" />
          </Form.Item>
          <Form.Item label="审计保留天数" name="audit_retention_days">
            <InputNumber min={1} max={365} style={{ width: 120 }} />
          </Form.Item>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadConfig}>
              重新加载
            </Button>
            <Button type="primary" icon={<SaveOutlined />} onClick={() => form.submit()} loading={configSaving}>
              保存配置
            </Button>
          </Space>
        </Card>
      </Form>

      <Card
        title="访问密钥"
        extra={
          <Button icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
            创建密钥
          </Button>
        }
        style={{ background: token.colorBgContainer, border: '1px solid #1e293b', marginTop: 16 }}
      >
        <Table
          rowKey="id"
          columns={keyColumns}
          dataSource={keys}
          loading={keysLoading}
          pagination={false}
        />
      </Card>

      <Modal
        title="创建访问密钥"
        open={createModalOpen}
        onOk={handleCreateKey}
        onCancel={() => { setCreateModalOpen(false); setNewKeyName(''); }}
        confirmLoading={creatingKey}
        okText="创建"
        cancelText="取消"
      >
        <Input
          placeholder="密钥名称"
          value={newKeyName}
          onChange={(e) => setNewKeyName(e.target.value)}
          onPressEnter={handleCreateKey}
        />
      </Modal>

      <Modal
        title="密钥配置"
        open={resultModalOpen}
        onCancel={() => setResultModalOpen(false)}
        footer={[
          <Button key="copy" icon={<CopyOutlined />} onClick={handleCopyConfig}>
            复制
          </Button>,
          <Button key="close" type="primary" onClick={() => setResultModalOpen(false)}>
            关闭
          </Button>,
        ]}
        width={600}
      >
        {createdResult && (
          <>
            <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
              {createdResult.note}
            </Text>
            <Input.TextArea
              rows={10}
              readOnly
              value={JSON.stringify(createdResult.mcp_config, null, 2)}
              style={{ fontFamily: 'monospace' }}
            />
          </>
        )}
      </Modal>

      <Card
        title="审计日志"
        extra={
          <Space>
            <Popconfirm title="确定清理过期审计日志？" onConfirm={handleCleanup}>
              <Button loading={cleanupLoading} danger>
                清理日志
              </Button>
            </Popconfirm>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => loadAuditLogs(0)}
            >
              刷新
            </Button>
          </Space>
        }
        style={{ background: token.colorBgContainer, border: '1px solid #1e293b', marginTop: 16 }}
      >
        <Table
          rowKey="id"
          columns={auditColumns}
          dataSource={auditLogs}
          loading={auditLoading}
          pagination={{
            pageSize: auditLimit,
            current: Math.floor(auditOffset / auditLimit) + 1,
            onChange: (page) => loadAuditLogs((page - 1) * auditLimit),
            showSizeChanger: false,
          }}
        />
      </Card>
    </div>
  );
}
