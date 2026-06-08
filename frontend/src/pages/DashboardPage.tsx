import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Row, Col, Statistic, Table, Tag, Button, Typography, Space, Empty } from 'antd';
import { ExperimentOutlined, CheckCircleOutlined, ClockCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { listSessions } from '@/api/sessions';
import type { SessionResponse, SessionStatus } from '@/types';

const statusColors: Record<SessionStatus, string> = {
  CREATED: 'default',
  READY: 'blue',
  RUNNING: 'processing',
  WAITING_INPUT: 'warning',
  CHECKPOINTING: 'purple',
  COMPLETED: 'success',
  FAILED: 'error',
  CANCELLED: 'default',
  CANCELLING: 'orange',
  TIMEOUT: 'error',
  ABORTED: 'error',
};

const statusLabels: Record<SessionStatus, string> = {
  CREATED: '已创建',
  READY: '就绪',
  RUNNING: '运行中',
  WAITING_INPUT: '等待输入',
  CHECKPOINTING: '检查点中',
  COMPLETED: '已完成',
  FAILED: '失败',
  CANCELLED: '已取消',
  CANCELLING: '取消中',
  TIMEOUT: '超时',
  ABORTED: '已中止',
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
  const runningCount = sessions.filter((s) => s.status === 'RUNNING').length;
  const completedCount = sessions.filter((s) => s.status === 'COMPLETED').length;

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
