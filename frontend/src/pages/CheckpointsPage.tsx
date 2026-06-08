import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Typography, Button, Space, Table, Tag, Timeline, Empty, Spin, Tooltip } from 'antd';
import { ArrowLeftOutlined, ReloadOutlined, HistoryOutlined } from '@ant-design/icons';
import client from '@/api/client';
import type { CheckpointRecord, CheckpointType } from '@/types';

async function getCheckpoints(sessionId: string): Promise<{ items: CheckpointRecord[] }> {
  const { data } = await client.get(`/sessions/${sessionId}/checkpoints`);
  return data;
}

const checkpointColors: Record<CheckpointType, string> = {
  STEP_COMPLETE: 'blue',
  TOOL_PRE: 'cyan',
  TOOL_POST: 'green',
  MANUAL: 'gold',
  PERIODIC: 'purple',
  CHATBACK_SNAPSHOT: 'magenta',
};

export default function CheckpointsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['checkpoints', sessionId],
    queryFn: () => getCheckpoints(sessionId!),
    enabled: !!sessionId,
  });

  const checkpoints = data?.items ?? [];

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  const columns = [
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 80,
      render: (v: number) => <Tag>v{v}</Tag>,
    },
    {
      title: '类型',
      dataIndex: 'checkpoint_type',
      key: 'type',
      render: (t: CheckpointType) => <Tag color={checkpointColors[t]}>{t}</Tag>,
    },
    {
      title: '状态摘要',
      dataIndex: 'state_summary',
      key: 'summary',
      ellipsis: true,
      render: (s: Record<string, unknown>) => (
        <Typography.Text code style={{ fontSize: 11 }}>{JSON.stringify(s).slice(0, 150)}</Typography.Text>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (t: string) => new Date(t).toLocaleString('zh-CN'),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/sessions/${sessionId}`)}>返回</Button>
          <Typography.Title level={4} style={{ margin: 0 }}>检查点时间线</Typography.Title>
        </Space>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
      </div>

      {checkpoints.length === 0 ? (
        <Card><Empty description="暂无检查点" /></Card>
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <Card title={<><HistoryOutlined /> 版本链时间线</>}>
            <Timeline
              items={checkpoints.map((cp) => ({
                color: checkpointColors[cp.checkpoint_type] ?? 'gray',
                children: (
                  <div>
                    <Space>
                      <Tag>v{cp.version}</Tag>
                      <Tag color={checkpointColors[cp.checkpoint_type]}>{cp.checkpoint_type}</Tag>
                      <Typography.Text type="secondary">{new Date(cp.created_at).toLocaleString('zh-CN')}</Typography.Text>
                    </Space>
                    <Tooltip title={JSON.stringify(cp.state_summary, null, 2)}>
                      <Typography.Paragraph ellipsis={{ rows: 1 }} type="secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 12 }}>
                        {JSON.stringify(cp.state_summary).slice(0, 100)}
                      </Typography.Paragraph>
                    </Tooltip>
                  </div>
                ),
              }))}
            />
          </Card>
          <Card title="检查点列表">
            <Table dataSource={checkpoints} columns={columns} rowKey="checkpoint_id" size="small" pagination={false} />
          </Card>
        </Space>
      )}
    </div>
  );
}
