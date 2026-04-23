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
  pending: '等待中',
  queued: '排队中',
  extracting_requirements: '提取需求',
  analyzing_risks: '风险分析',
  generating_report: '生成报告',
  completed: '已完成',
  failed: '失败',
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
      message.error('加载分析列表失败');
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
      message.success('正在重试分析');
      fetchAnalyses();
    } catch {
      message.error('重试失败');
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
      title: '预览',
      dataIndex: 'input_preview',
      key: 'input_preview',
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'input_type',
      key: 'input_type',
      render: (v: string) => <Tag>{v}</Tag>,
      width: 80,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: AnalysisStatus) => (
        <Tag color={STATUS_COLORS[status]}>{STATUS_LABELS[status]}</Tag>
      ),
      width: 120,
    },
    {
      title: '风险',
      dataIndex: 'risk_level',
      key: 'risk_level',
      render: (level: RiskLevel, record: AnalysisTask) => (
        <RiskBadge level={level} score={record.risk_score} showScore />
      ),
      width: 120,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
      width: 180,
    },
    {
      title: '操作',
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
              title="确认重试此分析？"
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
          分析列表
        </Title>
        <Button type="primary" onClick={() => navigate('/analyses/submit')}>
          新建分析
        </Button>
      </div>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索..."
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
          <Option value="all">全部状态</Option>
          <Option value="pending">等待中</Option>
          <Option value="queued">排队中</Option>
          <Option value="extracting_requirements">提取需求</Option>
          <Option value="analyzing_risks">风险分析</Option>
          <Option value="generating_report">生成报告</Option>
          <Option value="completed">已完成</Option>
          <Option value="failed">失败</Option>
        </Select>
      </Space>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
        </div>
      ) : filtered.length === 0 ? (
        <Empty description="暂无分析记录" />
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