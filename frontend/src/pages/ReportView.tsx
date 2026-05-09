import { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button,
  Typography,
  Spin,
  Empty,
  message,
  Dropdown,
} from 'antd';
import { ArrowLeftOutlined, DownloadOutlined, FilePdfOutlined, FileMarkdownOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import html2pdf from 'html2pdf.js';
import type { Report } from '@/types/api';
import { getReport } from '@/api/reports';
import { RiskBadge } from '@/components/RiskBadge';
import { ChatPanel } from '@/components/ChatPanel';
import { theme } from 'antd';

const { Title } = Typography;

export function ReportView() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const reportRef = useRef<HTMLDivElement>(null);
  const { token } = theme.useToken();

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

  const handleDownloadMD = () => {
    if (!report?.content_markdown) return;
    const blob = new Blob([report.content_markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report-${taskId}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadPDF = () => {
    if (!reportRef.current) return;
    
    message.loading({ content: '正在生成 PDF...', key: 'pdf-gen' });
    
    // 配置 html2pdf
    const opt = {
      margin:       15,
      filename:     `ReqRadar-Report-${taskId}.pdf`,
      image:        { type: 'jpeg' as const, quality: 0.98 },
      html2canvas:  { scale: 2, useCORS: true, letterRendering: true },
      jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' as const }
    };
    
    // 生成并下载
    html2pdf().set(opt).from(reportRef.current).save()
      .then(() => {
        message.success({ content: 'PDF 导出成功', key: 'pdf-gen' });
      })
      .catch((err: any) => {
        console.error('PDF generation failed:', err);
        message.error({ content: 'PDF 导出失败', key: 'pdf-gen' });
      });
  };

  const downloadMenu = {
    items: [
      {
        key: 'pdf',
        label: '导出 PDF',
        icon: <FilePdfOutlined />,
        onClick: handleDownloadPDF,
      },
      {
        key: 'md',
        label: '下载 Markdown',
        icon: <FileMarkdownOutlined />,
        onClick: handleDownloadMD,
      },
    ]
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
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 24px',
          background: token.colorBgContainer,
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
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
            <Title level={5} style={{ margin: 0 }}>
              任务 #{report.task_id} 分析报告
            </Title>
          </div>
          <RiskBadge level={report.risk_level as any} />
        </div>
        <Dropdown menu={downloadMenu} placement="bottomRight">
          <Button type="primary" icon={<DownloadOutlined />}>
            导出报告
          </Button>
        </Dropdown>
      </div>

      {/* scrollable report content */}
      <div
        ref={scrollRef}
        className="no-scrollbar"
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '32px 24px',
          background: token.colorBgBase,
        }}
      >
        <div style={{ maxWidth: 860, margin: '0 auto' }}>
          {report.content_markdown ? (
            <div className="markdown-body" ref={reportRef} style={{ background: token.colorBgContainer, padding: '40px 48px', borderRadius: token.borderRadiusLG, border: `1px solid ${token.colorBorderSecondary}` }}>
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
