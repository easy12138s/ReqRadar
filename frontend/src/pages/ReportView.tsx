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
        message.error('Failed to load report');
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
    return <Empty description="Report not found" />;
  }

  const tocItems = [
    { key: 'summary', href: '#summary', title: 'Summary' },
    { key: 'findings', href: '#findings', title: 'Findings' },
    { key: 'recommendations', href: '#recommendations', title: 'Recommendations' },
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
          Report
        </Title>
        <div>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/analyses')} style={{ marginRight: 8 }}>
            Back
          </Button>
          <Button icon={<DownloadOutlined />} onClick={handleDownload}>
            Download MD
          </Button>
        </div>
      </div>

      <Card style={{ marginBottom: 24 }}>
        <Title level={4}>{report.title}</Title>
        <Paragraph type="secondary">
          Generated on {new Date(report.created_at).toLocaleString()}
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
                    <Html5Outlined /> Rendered
                  </span>
                ),
                children: (
                  <div>
                    <section id="summary">
                      <Card title="Summary" style={{ marginBottom: 24 }}>
                        <Paragraph>{report.summary}</Paragraph>
                      </Card>
                    </section>

                    <section id="findings">
                      <Card title="Findings" style={{ marginBottom: 24 }}>
                        {report.findings.length === 0 ? (
                          <Empty description="No findings" />
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
                                <strong>Evidence:</strong> {finding.evidence}
                              </Paragraph>
                            </Card>
                          ))
                        )}
                      </Card>
                    </section>

                    <section id="recommendations">
                      <Card title="Recommendations">
                        {report.recommendations.length === 0 ? (
                          <Empty description="No recommendations" />
                        ) : (
                          report.recommendations.map((rec) => (
                            <Card
                              key={rec.id}
                              type="inner"
                              title={`Priority ${rec.priority}`}
                              style={{ marginBottom: 16 }}
                            >
                              <Paragraph>{rec.description}</Paragraph>
                              <Paragraph type="secondary">
                                <strong>Rationale:</strong> {rec.rationale}
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
                      <ReactMarkdown>{markdown || '# Report not available in markdown'}</ReactMarkdown>
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
