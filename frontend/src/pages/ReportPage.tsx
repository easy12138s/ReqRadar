import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Typography, Button, Space, Spin, Empty, Tag } from 'antd';
import { ArrowLeftOutlined, DownloadOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import client from '@/api/client';

interface ReportData {
  session_id: string;
  output_uri: string | null;
  content: string | null;
  format: string;
  generated_at: string | null;
}

async function getReport(sessionId: string): Promise<ReportData> {
  const { data } = await client.get(`/reports/${sessionId}/latest`);
  return data;
}

export default function ReportPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const { data: report, isLoading } = useQuery({
    queryKey: ['report', sessionId],
    queryFn: () => getReport(sessionId!),
    enabled: !!sessionId,
  });

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  if (!report || !report.content) {
    return (
      <div>
        <Space style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(`/sessions/${sessionId}`)}>返回</Button>
          <Typography.Title level={4} style={{ margin: 0 }}>分析报告</Typography.Title>
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
          <Tag>{report.format}</Tag>
        </Space>
        {report.output_uri && (
          <Button icon={<DownloadOutlined />} href={report.output_uri} target="_blank">下载</Button>
        )}
      </div>
      <Card>
        <div className="markdown-body" style={{ maxWidth: 900, margin: '0 auto' }}>
          <ReactMarkdown>{report.content}</ReactMarkdown>
        </div>
      </Card>
    </div>
  );
}
