import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Descriptions, Tag, Typography, Tabs, Table, Progress, Button, Space, Spin, Badge } from 'antd';
import { ReloadOutlined, StopOutlined, FileTextOutlined, UnorderedListOutlined } from '@ant-design/icons';
import { getSession, getSessionEvents, cancelSession } from '@/api/sessions';
import { getSessionEvidence } from '@/api/evidence';
import type { SessionStatus, EventRecord, DimensionStatus } from '@/types';

const statusColors: Record<SessionStatus, string> = {
  created: 'default',
  ready: 'blue',
  running: 'processing',
  waiting_input: 'warning',
  checkpointing: 'purple',
  completed: 'success',
  failed: 'error',
  cancelled: 'default',
  cancelling: 'orange',
  paused: 'default',
  timeout: 'error',
};

const statusLabels: Record<SessionStatus, string> = {
  created: '已创建',
  ready: '就绪',
  running: '运行中',
  waiting_input: '等待输入',
  checkpointing: '检查点中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  cancelling: '取消中',
  paused: '已暂停',
  timeout: '超时',
};

const dimensionLabels: Record<string, string> = {
  understanding: '需求理解',
  impact: '影响分析',
  risk: '风险评估',
  change: '变更管理',
  decision: '决策支持',
  evidence: '证据充分性',
  verification: '验证覆盖',
};

const dimensionStatusColors: Record<DimensionStatus, string> = {
  pending: '#d9d9d9',
  in_progress: '#1890ff',
  sufficient: '#52c41a',
  insufficient: '#ff4d4f',
};

export default function SessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const { data: session, isLoading, refetch } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => getSession(sessionId!),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' || status === 'checkpointing' ? 3000 : false;
    },
  });

  const { data: eventsData } = useQuery({
    queryKey: ['session-events', sessionId],
    queryFn: () => getSessionEvents(sessionId!, 50),
    enabled: !!sessionId,
    refetchInterval: session?.status === 'running' ? 5000 : false,
  });

  const { data: evidenceData } = useQuery({
    queryKey: ['session-evidence', sessionId],
    queryFn: () => getSessionEvidence(sessionId!),
    enabled: !!sessionId,
  });

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!session) return <Typography.Text>Session 不存在</Typography.Text>;

  const events = eventsData?.events ?? [];
  const evidence = evidenceData?.items ?? [];

  const eventColumns = [
    { title: '时间', dataIndex: 'created_at' as const, key: 'time', width: 180, render: (t: string) => new Date(t).toLocaleTimeString('zh-CN') },
    { title: '类型', dataIndex: 'event_type' as const, key: 'type', render: (t: string) => <Tag>{t}</Tag> },
    { title: '级别', dataIndex: 'level' as const, key: 'level', width: 80 },
    { title: '来源', dataIndex: 'producer' as const, key: 'producer', width: 120 },
    { title: '详情', dataIndex: 'payload' as const, key: 'payload', render: (p: Record<string, unknown>) => <Typography.Text code style={{ fontSize: 12 }}>{JSON.stringify(p).slice(0, 100)}</Typography.Text> },
  ];

  const evidenceColumns = [
    { title: 'ID', dataIndex: 'evidence_id' as const, key: 'id', width: 200, render: (id: string) => <Typography.Text code style={{ fontSize: 11 }}>{id.slice(0, 12)}...</Typography.Text> },
    { title: '类型', dataIndex: 'evidence_type' as const, key: 'type', render: (t: string) => <Tag>{t}</Tag> },
    { title: '来源', dataIndex: 'source' as const, key: 'source', width: 120 },
    { title: '置信度', dataIndex: 'confidence' as const, key: 'confidence', width: 100, render: (c: number) => <Progress percent={Math.round(c * 100)} size="small" /> },
    { title: '内容摘要', dataIndex: 'content' as const, key: 'content', ellipsis: true },
  ];

  const isRunning = session.status === 'running' || session.status === 'checkpointing';

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Typography.Title level={4} style={{ margin: 0 }}>Session 详情</Typography.Title>
          <Tag color={statusColors[session.status]}>{statusLabels[session.status]}</Tag>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
          {isRunning && <Button danger icon={<StopOutlined />} onClick={() => cancelSession(sessionId!)}>取消</Button>}
          <Button icon={<FileTextOutlined />} onClick={() => navigate(`/sessions/${sessionId}/report`)}>查看报告</Button>
          <Button icon={<UnorderedListOutlined />} onClick={() => navigate(`/sessions/${sessionId}/events`)}>全部事件</Button>
        </Space>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="Session ID"><Typography.Text code>{session.session_id}</Typography.Text></Descriptions.Item>
          <Descriptions.Item label="项目 ID"><Typography.Text code>{session.project_id}</Typography.Text></Descriptions.Item>
          <Descriptions.Item label="用户">{session.user_id}</Descriptions.Item>
          <Descriptions.Item label="推理步骤">{session.total_reasoning_steps}</Descriptions.Item>
          <Descriptions.Item label="检查点版本">{session.last_checkpoint_version}</Descriptions.Item>
          <Descriptions.Item label="创建时间">{new Date(session.created_at).toLocaleString('zh-CN')}</Descriptions.Item>
          {session.started_at && <Descriptions.Item label="启动时间">{new Date(session.started_at).toLocaleString('zh-CN')}</Descriptions.Item>}
          {session.finished_at && <Descriptions.Item label="完成时间">{new Date(session.finished_at).toLocaleString('zh-CN')}</Descriptions.Item>}
          {session.error_message && <Descriptions.Item label="错误"><Typography.Text type="danger">{session.error_message}</Typography.Text></Descriptions.Item>}
        </Descriptions>
      </Card>

      <Tabs
        defaultActiveKey="timeline"
        items={[
          {
            key: 'timeline',
            label: `推理时间线 (${events.length})`,
            children: (
              <Card>
                <Table<EventRecord> dataSource={events} columns={eventColumns} rowKey="id" size="small" pagination={{ pageSize: 20 }} />
              </Card>
            ),
          },
          {
            key: 'evidence',
            label: `证据列表 (${evidence.length})`,
            children: (
              <Card>
                <Table dataSource={evidence} columns={evidenceColumns} rowKey="evidence_id" size="small" pagination={{ pageSize: 20 }} />
              </Card>
            ),
          },
          {
            key: 'dimensions',
            label: '七维度面板',
            children: (
              <Card>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
                  {Object.entries(dimensionLabels).map(([key, label]) => (
                    <Card key={key} size="small" hoverable>
                      <div style={{ textAlign: 'center' }}>
                        <Badge color={dimensionStatusColors.pending} />
                        <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>{label}</Typography.Text>
                        <Typography.Text type="secondary">待接入 WS</Typography.Text>
                      </div>
                    </Card>
                  ))}
                </div>
              </Card>
            ),
          },
          {
            key: 'requirement',
            label: '需求文本',
            children: (
              <Card>
                <Typography.Paragraph>{session.requirement_text || '无需求文本'}</Typography.Paragraph>
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}
