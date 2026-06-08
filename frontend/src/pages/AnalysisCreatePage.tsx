import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { Card, Form, Input, Button, Typography, message, Select, Divider, Space } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { createSession, startSession } from '@/api/sessions';

export default function AnalysisCreatePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [createdSessionId, setCreatedSessionId] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: createSession,
    onSuccess: (session) => {
      setCreatedSessionId(session.session_id);
      message.success('Session 创建成功');
    },
    onError: () => message.error('创建失败'),
  });

  const startMutation = useMutation({
    mutationFn: (sessionId: string) => startSession(sessionId),
    onSuccess: (session) => {
      message.success('分析已启动');
      navigate(`/sessions/${session.session_id}`);
    },
    onError: () => message.error('启动失败'),
  });

  const handleCreate = async () => {
    const values = await form.validateFields();
    createMutation.mutate({
      project_id: values.project_id || 'default',
      requirement_text: values.requirement_text,
      config: values.depth ? { depth: values.depth } : undefined,
    });
  };

  const handleStart = () => {
    if (createdSessionId) {
      startMutation.mutate(createdSessionId);
    }
  };

  return (
    <div>
      <Typography.Title level={4}>新建分析</Typography.Title>
      <Card style={{ maxWidth: 800 }}>
        <Form form={form} layout="vertical" initialValues={{ depth: 'standard' }}>
          <Form.Item name="project_id" label="项目 ID" rules={[{ required: true, message: '请输入项目 ID' }]}>
            <Input placeholder="项目 UUID" />
          </Form.Item>
          <Form.Item name="requirement_text" label="需求文本" rules={[{ required: true, message: '请输入需求描述' }]}>
            <Input.TextArea rows={8} placeholder="粘贴需求文档内容或描述分析目标..." />
          </Form.Item>
          <Form.Item name="depth" label="分析深度">
            <Select
              options={[
                { value: 'quick', label: '快速扫描' },
                { value: 'standard', label: '标准分析' },
                { value: 'deep', label: '深度分析' },
              ]}
            />
          </Form.Item>
          <Divider />
          <Space>
            <Button
              type="primary"
              onClick={handleCreate}
              loading={createMutation.isPending}
              disabled={!!createdSessionId}
            >
              创建 Session
            </Button>
            {createdSessionId && (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleStart}
                loading={startMutation.isPending}
              >
                启动分析
              </Button>
            )}
          </Space>
        </Form>
      </Card>
    </div>
  );
}
