import { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button,
  Typography,
  Spin,
  Empty,
  message,
  Dropdown,
  Modal,
  Input,
  Form,
} from 'antd';
import { ArrowLeftOutlined, DownloadOutlined, FilePdfOutlined, FileMarkdownOutlined, PlusOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import html2pdf from 'html2pdf.js';
import type { Report } from '@/types/api';
import { getReport } from '@/api/reports';
import { createRelease, publishRelease } from '@/api/releases';
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
  const [releaseModalOpen, setReleaseModalOpen] = useState(false);
  const [releaseForm] = Form.useForm();
  const [releaseLoading, setReleaseLoading] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [chatHeight, setChatHeight] = useState(320);
  const chatRef = useRef<HTMLDivElement>(null);
  const dragStartY = useRef(0);
  const dragStartHeight = useRef(0);
  const isDragging = useRef(false);

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
      .catch((err: unknown) => {
        console.error('PDF generation failed:', err);
        message.error({ content: 'PDF 导出失败', key: 'pdf-gen' });
      });
  };

  const handleReleaseSubmit = async () => {
    try {
      const values = await releaseForm.validateFields();
      setReleaseLoading(true);
      const release = await createRelease({
        project_id: Number(values.project_id),
        release_code: values.release_code,
        title: values.title,
        content: report?.content_markdown || '',
        task_id: taskId ? Number(taskId) : undefined,
      });
      await publishRelease(release.id);
      message.success('需求版本已创建并发布');
      setReleaseModalOpen(false);
      releaseForm.resetFields();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      if (err?.response?.data?.detail) {
        message.error(err.response.data.detail);
      }
    } finally {
      setReleaseLoading(false);
    }
  };

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = true;
    dragStartY.current = e.clientY;
    dragStartHeight.current = chatHeight;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'row-resize';
  }, [chatHeight]);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging.current) return;
    const delta = dragStartY.current - e.clientY;
    const newHeight = Math.max(120, Math.min(600, dragStartHeight.current + delta));
    setChatHeight(newHeight);
  }, []);

  const handleMouseUp = useCallback(() => {
    if (isDragging.current) {
      isDragging.current = false;
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    }
  }, []);

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleMouseMove, handleMouseUp]);

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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
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
            aria-label="返回分析列表"
          />
          <div>
            <Title level={5} style={{ margin: 0 }}>
              任务 #{report.task_id} 分析报告
            </Title>
          </div>
          <RiskBadge level={report.risk_level as 'low' | 'medium' | 'high' | 'critical'} />
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button icon={<PlusOutlined />} onClick={() => setReleaseModalOpen(true)}>
            发布为需求版本
          </Button>
          <Dropdown menu={downloadMenu} placement="bottomRight">
            <Button type="primary" icon={<DownloadOutlined />}>
              导出报告
            </Button>
          </Dropdown>
        </div>
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
          minHeight: 0,
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

      {/* collapsible & resizable chat panel */}
      <div
        ref={chatRef}
        style={{
          borderTop: `1px solid ${token.colorBorderSecondary}`,
          background: token.colorBgContainer,
          flexShrink: 0,
          height: chatCollapsed ? 48 : chatHeight,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          transition: chatCollapsed ? 'height 0.3s ease' : 'none',
        }}
      >
        {/* drag handle */}
        <div
          onMouseDown={handleMouseDown}
          onClick={() => setChatCollapsed(!chatCollapsed)}
          style={{
            height: 8,
            background: chatCollapsed ? 'transparent' : `${token.colorBorderSecondary}`,
            cursor: 'row-resize',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            transition: 'background 0.2s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = `${token.colorPrimary}40`; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = chatCollapsed ? 'transparent' : `${token.colorBorderSecondary}`; }}
        >
          <div style={{
            width: 40,
            height: 4,
            borderRadius: 2,
            background: token.colorTextSecondary,
            opacity: 0.5,
          }} />
        </div>
        {/* chat header bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 16px',
            borderBottom: chatCollapsed ? 'none' : `1px solid ${token.colorBorderSecondary}`,
            flexShrink: 0,
            cursor: 'pointer',
          }}
          onClick={() => setChatCollapsed(!chatCollapsed)}
        >
          <span style={{ fontSize: 13, fontWeight: 600, color: token.colorText }}>
            AI 追问助手
          </span>
          <Button type="text" size="small" style={{ color: token.colorTextSecondary }}>
            {chatCollapsed ? '展开' : '收起'}
          </Button>
        </div>
        {/* chat content */}
        {!chatCollapsed && (
          <div style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
            <ChatPanel taskId={taskId} />
          </div>
        )}
      </div>

      <Modal
        title="发布为需求版本"
        open={releaseModalOpen}
        onCancel={() => {
          setReleaseModalOpen(false);
          releaseForm.resetFields();
        }}
        onOk={handleReleaseSubmit}
        confirmLoading={releaseLoading}
        okText="创建并发布"
      >
        <Form form={releaseForm} layout="vertical">
          <Form.Item label="项目 ID" name="project_id" rules={[{ required: true, message: '请输入项目 ID' }]}>
            <Input type="number" />
          </Form.Item>
          <Form.Item label="版本代号" name="release_code" rules={[{ required: true, message: '请输入版本代号' }]}>
            <Input placeholder="例如: REQ-2026-001" />
          </Form.Item>
          <Form.Item label="标题" name="title" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="需求版本标题" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
