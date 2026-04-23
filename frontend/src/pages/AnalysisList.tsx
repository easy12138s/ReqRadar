import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table,
  Button,
  Typography,
  Tag,
  Space,
  Input,
  Select,
  Spin,
  Empty,
  message,
  Popconfirm,
} from 'antd';
import {
  EyeOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import type { AnalysisTask, AnalysisStatus, RiskLevel } from '@/types/api';
import { getAnalyses, retryAnalysis } from '@/api/analyses';
import { RiskBadge } from '@/components/RiskBadge';

const { Title } = Typography;
const { Option } = Select;

const STATUS_COLORS: Record<AnalysisStatus, string> = {
  pending: 'default',
  queued: 'processing',
  extracting_requirements: 'processing',
  analyzing_risks: 'warning',
  generating_report: 'warning',
  completed: 'success',
  failed: 'error',
};

const STATUS_LABELS: Record<AnalysisStatus, string> = {
  pending: 'Pending',
  queued: 'Queued',
  extracting_requirements: 'Extracting',
  analyzing_risks: 'Analyzing',
  generating_report: 'Reporting',
  completed: 'Completed',
  failed: 'Failed',
};

export function AnalysisList() {
  const [analyses, setAnalyses] = useState<AnalysisTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<AnalysisStatus | 'all'>('all');
  const [searchText, setSearchText] = useState('');
  const navigate = useNavigate();

  const fetchAnalyses = async () => {
    setLoading(true);
    try {
      const data = await getAnalyses();
      setAnalyses(data);
    } catch {
      message.error('Failed to load analyses');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalyses();
  }, []);

  const handleRetry = async (id: string) => {
    try {
      await retryAnalysis(id);
      message.success('Analysis retrying');
      fetchAnalyses();
    } catch {
      message.error('Failed to retry analysis');
    }
  };

  const filtered = analyses.filter((a) => {
    const matchesStatus = statusFilter === 'all' || a.status === statusFilter;
    const matchesSearch =
      !searchText ||
      a.input_preview.toLowerCase().includes(searchText.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      ellipsis: true,
      width: 80,
    },
    {
      title: 'Preview',
      dataIndex: 'input_preview',
      key: 'input_preview',
      ellipsis: true,
    },
    {
      title: 'Type',
      dataIndex: 'input_type',
      key: 'input_type',
      render: (v: string) => <Tag>{v}</Tag>,
      width: 80,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: AnalysisStatus) => (
        <Tag color={STATUS_COLORS[status]}>{STATUS_LABELS[status]}</Tag>
      ),
      width: 120,
    },
    {
      title: 'Risk',
      dataIndex: 'risk_level',
      key: 'risk_level',
      render: (level: RiskLevel, record: AnalysisTask) => (
        <RiskBadge level={level} score={record.risk_score} showScore />
      ),
      width: 120,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
      width: 180,
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: AnalysisTask) => (
        <Space>
          <Button
            type="text"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/analyses/${record.id}`)}
          />
          {record.status === 'failed' && (
            <Popconfirm
              title="Retry this analysis?"
              onConfirm={() => handleRetry(record.id)}
            >
              <Button type="text" icon={<ReloadOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
      width: 100,
    },
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
          Analyses
        </Title>
        <Button type="primary" onClick={() => navigate('/analyses/submit')}>
          New Analysis
        </Button>
      </div>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="Search..."
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={{ width: 240 }}
          allowClear
        />
        <Select
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 140 }}
        >
          <Option value="all">All Statuses</Option>
          <Option value="pending">Pending</Option>
          <Option value="queued">Queued</Option>
          <Option value="extracting_requirements">Extracting</Option>
          <Option value="analyzing_risks">Analyzing</Option>
          <Option value="generating_report">Reporting</Option>
          <Option value="completed">Completed</Option>
          <Option value="failed">Failed</Option>
        </Select>
      </Space>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : filtered.length === 0 ? (
        <Empty description="No analyses found" />
      ) : (
        <Table
          dataSource={filtered}
          columns={columns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          scroll={{ x: true }}
        />
      )}
    </div>
  );
}
