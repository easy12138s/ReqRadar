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
  Tabs,
} from 'antd';
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  FileMarkdownOutlined,
  Html5Outlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import type { Report } from '@/types/api';
import { getReport, getReportMarkdown } from '@/api/reports';
import { RiskBadge } from '@/components/RiskBadge';

const { Title, Paragraph } = Typography;

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
    { key: 'summary', href: '#summary', title: '摘要' },
    { key: 'findings', href: '#findings', title: '发现' },
    { key: 'recommendations', href: '#recommendations', title: '建议' },
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
        <Title level={4}>{report.title}</Title>
        <Paragraph type="secondary">
          生成时间: {new Date(report.created_at).toLocaleString()}
        </Paragraph>
      </Card>

      <div style={{ display: 'flex', gap: 24 }}>
        <div style={{ width: 200, flexShrink: 0 }}>
          <Anchor items={tocItems} />
        </div>
        <div style={{ flex: 1 }} ref={contentRef}>
          <Tabs
            items={[
              {
                key: 'rendered',
                label: (
                  <span>
                    <Html5Outlined /> 渲染视图
                  </span>
                ),
                children: (
                  <div>
                    <section id="summary">
                      <Card title="摘要" style={{ marginBottom: 24 }}>
                        <Paragraph>{report.summary}</Paragraph>
                      </Card>
                    </section>

                    <section id="findings">
                      <Card title="发现" style={{ marginBottom: 24 }}>
                        {report.findings.length === 0 ? (
                          <Empty description="暂无发现" />
                        ) : (
                          report.findings.map((finding) => (
                            <Card
                              key={finding.id}
                              type="inner"
                              title={finding.category}
                              style={{ marginBottom: 16 }}
                              extra={<RiskBadge level={finding.risk_level} />}
                            >
                              <Paragraph>{finding.description}</Paragraph>
                              <Paragraph type="secondary">
                                <strong>证据：</strong> {finding.evidence}
                              </Paragraph>
                            </Card>
                          ))
                        )}
                      </Card>
                    </section>

                    <section id="recommendations">
                      <Card title="建议">
                        {report.recommendations.length === 0 ? (
                          <Empty description="暂无建议" />
                        ) : (
                          report.recommendations.map((rec) => (
                            <Card
                              key={rec.id}
                              type="inner"
                              title={`优先级 ${rec.priority}`}
                              style={{ marginBottom: 16 }}
                            >
                              <Paragraph>{rec.description}</Paragraph>
                              <Paragraph type="secondary">
                                <strong>理由：</strong> {rec.rationale}
                              </Paragraph>
                            </Card>
                          ))
                        )}
                      </Card>
                    </section>
                  </div>
                ),
              },
              {
                key: 'markdown',
                label: (
                  <span>
                    <FileMarkdownOutlined /> Markdown
                  </span>
                ),
                children: (
                  <Card>
                    <div className="markdown-body">
                      <ReactMarkdown>{markdown || '# 报告暂无 Markdown 内容'}</ReactMarkdown>
                    </div>
                  </Card>
                ),
              },
            ]}
          />
        </div>
      </div>
    </div>
  );
}