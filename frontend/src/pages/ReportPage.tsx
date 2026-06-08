import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Card, Typography, Button, Space, Spin, Empty, Tag, Alert } from 'antd';
import { ArrowLeftOutlined, DownloadOutlined, ReloadOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import client from '@/api/client';

interface ReportTaskResponse {
  task_id: string;
  status?: string;
  session_id?: string;
  output_uri?: string | null;
  content?: string | null;
  format?: string;
  generated_at?: string | null;
  error?: string | null;
}

async function generateReport(sessionId: string): Promise<ReportTaskResponse> {
  const { data } = await client.post('/reports/generate', {
    session_id: sessionId,
    output_format: 'markdown',
  });
  return data;
}

async function getReportStatus(taskId: string): Promise<ReportTaskResponse> {
  const { data } = await client.get(`/reports/${taskId}/status`);
  return data;
}

export default function ReportPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const generateMutation = useMutation({
    mutationFn: () => generateReport(sessionId!),
  });

  useEffect(() => {
    if (sessionId && !generateMutation.data && !generateMutation.isPending) {
      generateMutation.mutate();
    }
  }, [sessionId]);

  const taskId = generateMutation.data?.task_id;

  const { data: reportStatus, isLoading: statusLoading } = useQuery({
    queryKey: ['report-status', taskId],
    queryFn: () => getReportStatus(taskId!),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const st = query.state.data?.status;
      return st === 'pending' || st === 'running' || st === 'generating' ? 3000 : false;
    },
  });

  const isLoading = generateMutation.isPending || statusLoading;
  const error = generateMutation.error;

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  if (error) {
    return (
      <div>
        <Space style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/sessions/${sessionId}`)}>返回</Button>
          <Typography.Title level={4} style={{ margin: 0 }}>分析报告</Typography.Title>
        </Space>
        <Card>
          <Alert type="error" message="报告生成失败" description={String(error)} />
        </Card>
      </div>
    );
  }

  const content = reportStatus?.content ?? null;
  const format = reportStatus?.format ?? 'markdown';
  const outputUri = reportStatus?.output_uri ?? null;
  const generatedAt = reportStatus?.generated_at ?? null;

  if (!content) {
    return (
      <div>
        <Space style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/sessions/${sessionId}`)}>返回</Button>
          <Typography.Title level={4} style={{ margin: 0 }}>分析报告</Typography.Title>
          <Button icon={<ReloadOutlined />} onClick={() => generateMutation.mutate()}>重新生成</Button>
        </Space>
        <Card>
          <Empty description="报告尚未生成，请等待分析完成后查看" />
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/sessions/${sessionId}`)}>返回</Button>
          <Typography.Title level={4} style={{ margin: 0 }}>分析报告</Typography.Title>
          <Tag>{format}</Tag>
          {generatedAt && <Tag color="blue">{new Date(generatedAt).toLocaleString('zh-CN')}</Tag>}
        </Space>
        {outputUri && (
          <Button icon={<DownloadOutlined />} href={outputUri} target="_blank">下载</Button>
        )}
      </div>
      <Card>
        <div className="markdown-body" style={{ maxWidth: 900, margin: '0 auto' }}>
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>
      </Card>
    </div>
  );
}
