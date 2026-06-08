import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Row, Col, Statistic, Table, Tag, Button, Typography, Space, Empty } from 'antd';
import { ExperimentOutlined, CheckCircleOutlined, ClockCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { listSessions } from '@/api/sessions';
import type { SessionResponse, SessionStatus } from '@/types';

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

export default function DashboardPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const { data, isLoading } = useQuery({
    queryKey: ['sessions', { page, limit: pageSize }],
    queryFn: () => listSessions({ limit: 50 }),
    refetchInterval: 10000,
  });

  const sessions = data?.sessions ?? [];
  const runningCount = sessions.filter((s) => s.status === 'running').length;
  const completedCount = sessions.filter((s) => s.status === 'completed').length;

  const columns = [
    {
      title: 'Session ID',
      dataIndex: 'session_id',
      key: 'session_id',
      render: (id: string) => (
        <Typography.Text copyable={{ text: id }} style={{ fontFamily: 'monospace', fontSize: 12 }}>
          {id.slice(0, 8)}...
        </Typography.Text>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: SessionStatus) => <Tag color={statusColors[status]}>{statusLabels[status] ?? status}</Tag>,
    },
    {
      title: '推理步骤',
      dataIndex: 'total_reasoning_steps',
      key: 'steps',
      width: 100,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string) => new Date(t).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: SessionResponse) => (
        <Space>
          <Button size="small" type="link" onClick={() => navigate(`/sessions/${record.session_id}`)}>详情</Button>
          <Button size="small" type="link" onClick={() => navigate(`/sessions/${record.session_id}/report`)}>报告</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4}>工作台</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/analysis/new')}>新建分析</Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic title="总 Session 数" value={sessions.length} prefix={<ExperimentOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="运行中" value={runningCount} prefix={<ClockCircleOutlined />} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="已完成" value={completedCount} prefix={<CheckCircleOutlined />} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
      </Row>

      <Card title="最近 Session">
        {sessions.length === 0 && !isLoading ? (
          <Empty description="暂无 Session，点击上方按钮创建" />
        ) : (
          <Table
            dataSource={sessions}
            columns={columns}
            rowKey="session_id"
            loading={isLoading}
            pagination={{ current: page, pageSize, total: sessions.length, onChange: setPage }}
            size="small"
          />
        )}
      </Card>
    </div>
  );
}
