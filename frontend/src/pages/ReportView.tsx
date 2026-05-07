import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  Typography,
  Spin,
  Empty,
  Anchor,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import type { Report } from '@/types/api';
import { getReport, getReportMarkdown } from '@/api/reports';
import { RiskBadge } from '@/components/RiskBadge';

const { Title } = Typography;

export function ReportView() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<Report | null>(null);
  const [markdown, setMarkdown] = useState('');
  const [loading, setLoading] = useState(true);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchReport = async () => {
      if (!taskId) return;
      setLoading(true);
      try {
        const [reportData, mdData] = await Promise.all([
          getReport(taskId),
          getReportMarkdown(taskId).catch(() => ''),
        ]);
        setReport(reportData);
        setMarkdown(mdData);
      } catch {
        message.error('加载报告失败');
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [taskId]);

  const handleDownload = () => {
    if (!markdown) return;
    const blob = new Blob([markdown], { type: 'text/markdown' });
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
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!report) {
    return <Empty description="报告未找到" />;
  }

  const tocItems = [
    { key: 'report', href: '#report-content', title: '报告' },
  ];

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          分析报告
        </Title>
        <div>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/analyses')} style={{ marginRight: 8 }}>
            返回
          </Button>
          <Button icon={<DownloadOutlined />} onClick={handleDownload}>
            下载 MD
          </Button>
        </div>
      </div>

      <Card style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={5} style={{ margin: 0 }}>任务 #{report.task_id} 分析报告</Title>
          </div>
          <RiskBadge level={report.risk_level as any} />
        </div>
      </Card>

      <div style={{ display: 'flex', gap: 24 }}>
        <div style={{ width: 180, flexShrink: 0 }}>
          <Anchor
            items={tocItems}
            onClick={(e, link) => {
              e.preventDefault();
              const el = document.getElementById(link.href.split('#')[1]);
              if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }}
          />
        </div>
        <div style={{ flex: 1 }} ref={contentRef}>
          <Card id="report-content">
            <div className="markdown-body">
              {markdown ? (
                <ReactMarkdown>{markdown}</ReactMarkdown>
              ) : (
                <Empty description="报告内容为空" />
              )}
            </div>
          </Card>
        </div>
      </div>

    </div>
  );
}