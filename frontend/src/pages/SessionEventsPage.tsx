import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Tag, Typography, Button, Space, Select, Badge } from 'antd';
import { ArrowLeftOutlined, ReloadOutlined, WifiOutlined } from '@ant-design/icons';
import { getSessionEvents } from '@/api/sessions';
import { useSessionWebSocket } from '@/hooks/useSessionWebSocket';
import type { EventType, EventLevel, EventRecord, WsEvent } from '@/types';

const eventTypeColors: Partial<Record<EventType, string>> = {
  SESSION_CREATED: 'blue',
  SESSION_STARTED: 'green',
  SESSION_CHECKPOINTED: 'gold',
  SESSION_COMPLETED: 'success',
  SESSION_FAILED: 'error',
  SESSION_CANCELLING: 'orange',
  SESSION_CANCELLED: 'default',
  SESSION_TIMEOUT: 'error',
  SESSION_ABORTED: 'error',
  SESSION_WAITING_INPUT: 'warning',
  SESSION_RESUMED: 'cyan',
  STEP_STARTED: 'processing',
  STEP_COMPLETED: 'cyan',
  TOOL_INVOKED: 'geekblue',
  TOOL_RETURNED: 'green',
  TOOL_RETRY: 'orange',
  TOOL_TIMEOUT: 'error',
  TOOL_PERMISSION_DENIED: 'red',
  TOOL_CHECKPOINT_FAILED: 'volcano',
  CONTEXT_COLLECTED: 'purple',
  CONTEXT_SCORED: 'lime',
  EVIDENCE_ADDED: 'magenta',
  DIMENSION_CHANGED: 'gold',
};

export default function SessionEventsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [typeFilter, setTypeFilter] = useState<string | undefined>();
  const [levelFilter, setLevelFilter] = useState<string | undefined>();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['session-events', sessionId, typeFilter, levelFilter],
    queryFn: () => getSessionEvents(sessionId!, 200),
    enabled: !!sessionId,
  });

  const { state: wsState, events: wsEvents } = useSessionWebSocket({
    sessionId: sessionId!,
    enabled: !!sessionId,
  });

  const allEvents: (EventRecord | WsEvent)[] = [
    ...(data?.events ?? []),
    ...wsEvents.filter((we) => !data?.events?.some((e) => e.event_type === we.event_type && e.created_at === we.timestamp)),
  ];

  const filtered = allEvents.filter((e) => {
    if (typeFilter && e.event_type !== typeFilter) return false;
    if (levelFilter && e.level !== levelFilter) return false;
    return true;
  });

  const columns = [
    {
      title: '时间',
      key: 'time',
      width: 180,
      render: (_: unknown, r: EventRecord | WsEvent) => {
        const t = 'created_at' in r ? r.created_at : r.timestamp;
        return new Date(t).toLocaleString('zh-CN');
      },
    },
    {
      title: '类型',
      dataIndex: 'event_type',
      key: 'type',
      render: (t: EventType) => <Tag color={eventTypeColors[t]}>{t}</Tag>,
    },
    {
      title: '级别',
      dataIndex: 'level',
      key: 'level',
      width: 80,
      render: (l: EventLevel) => <Tag>{l}</Tag>,
    },
    {
      title: '来源',
      dataIndex: 'producer',
      key: 'producer',
      width: 120,
    },
    {
      title: '载荷',
      key: 'payload',
      ellipsis: true,
      render: (_: unknown, r: EventRecord | WsEvent) => (
        <Typography.Text code style={{ fontSize: 11 }}>
          {JSON.stringify(r.payload).slice(0, 120)}
        </Typography.Text>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/sessions/${sessionId}`)}>返回</Button>
          <Typography.Title level={4} style={{ margin: 0 }}>事件流</Typography.Title>
          <Badge status={wsState.connected ? 'success' : 'default'} text={
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              <WifiOutlined /> {wsState.connected ? '实时' : wsState.reconnecting ? '重连中...' : '离线'}
            </Typography.Text>
          } />
        </Space>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
      </div>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Select placeholder="事件类型" allowClear style={{ width: 200 }} value={typeFilter} onChange={setTypeFilter}
            options={[
              'SESSION_CREATED', 'SESSION_STARTED', 'SESSION_CHECKPOINTED', 'SESSION_COMPLETED',
              'SESSION_FAILED', 'SESSION_CANCELLING', 'SESSION_CANCELLED', 'SESSION_TIMEOUT',
              'SESSION_ABORTED', 'SESSION_WAITING_INPUT', 'SESSION_RESUMED',
              'STEP_STARTED', 'STEP_COMPLETED',
              'TOOL_INVOKED', 'TOOL_RETURNED', 'TOOL_RETRY', 'TOOL_TIMEOUT',
              'TOOL_PERMISSION_DENIED', 'TOOL_CHECKPOINT_FAILED',
              'CONTEXT_COLLECTED', 'CONTEXT_SCORED',
              'EVIDENCE_ADDED', 'DIMENSION_CHANGED',
            ].map((t) => ({ value: t, label: t }))}
          />
          <Select placeholder="事件级别" allowClear style={{ width: 120 }} value={levelFilter} onChange={setLevelFilter}
            options={['session', 'reasoning', 'cognitive'].map((l) => ({ value: l, label: l }))}
          />
        </Space>
        <Table
          dataSource={filtered}
          columns={columns}
          rowKey={(r) => 'id' in r ? r.id : `${r.event_type}-${r.timestamp}`}
          loading={isLoading}
          size="small"
          pagination={{ pageSize: 50 }}
        />
      </Card>
    </div>
  );
}
