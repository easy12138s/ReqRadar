import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button,
  Typography,
  Spin,
  Empty,
  message,
} from 'antd';
import { ArrowLeftOutlined, DownloadOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import type { Report } from '@/types/api';
import { getReport } from '@/api/reports';
import { RiskBadge } from '@/components/RiskBadge';
import { ChatPanel } from '@/components/ChatPanel';

const { Title } = Typography;

export function ReportView() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!taskId) return;
    setLoading(true);
    (async () => {
      try {
        const reportData = await getReport(taskId);
        setReport(reportData);
      } catch {
        message.error('加载报告失败');
      } finally {
        setLoading(false);
      }
    })();
  }, [taskId]);

  const handleDownload = () => {
    if (!report?.content_markdown) return;
    const blob = new Blob([report.content_markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report-${taskId}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!taskId) {
    return <Empty description="无效的任务 ID" />;
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!report) {
    return <Empty description="报告未找到" />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)' }}>
      {/* top bar */}
      <div
        className="glass"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 20px',
          borderBottom: '1px solid #363b48',
          borderRadius: '12px 12px 0 0',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/analyses')}
          />
          <div>
            <Title level={5} style={{ margin: 0, color: '#f0f6fc' }}>
              任务 #{report.task_id} 分析报告
            </Title>
          </div>
          <RiskBadge level={report.risk_level as any} />
        </div>
        <Button icon={<DownloadOutlined />} onClick={handleDownload}>
          下载 MD
        </Button>
      </div>

      {/* scrollable report content */}
      <div
        ref={scrollRef}
        className="no-scrollbar"
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '32px 24px',
          background: '#0d1117',
        }}
      >
        <div style={{ maxWidth: 860, margin: '0 auto' }}>
          {report.content_markdown ? (
            <div className="markdown-body">
              <ReactMarkdown>{report.content_markdown}</ReactMarkdown>
            </div>
          ) : (
            <Empty description="报告内容为空" />
          )}
        </div>
      </div>

      {/* fixed bottom chat */}
      <div
        style={{
          borderTop: '1px solid #363b48',
          background: '#0d1117',
          flexShrink: 0,
          maxHeight: '40vh',
          overflow: 'auto',
        }}
      >
        <ChatPanel taskId={taskId} />
      </div>
    </div>
  );
}
