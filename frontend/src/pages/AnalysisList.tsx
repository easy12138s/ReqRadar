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
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import type { AnalysisTask } from '@/types/api';
import { getAnalyses, retryAnalysis } from '@/api/analyses';

const { Title } = Typography;

const STATUS_COLORS: Record<string, string> = {
  pending: 'default',
  running: 'processing',
  completed: 'success',
  failed: 'error',
  cancelled: 'warning',
};

const STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

export function AnalysisList() {
  const [analyses, setAnalyses] = useState<AnalysisTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
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

  const handleRetry = async (id: number) => {
    try {
      const res = await retryAnalysis(String(id));
      message.success('正在重试分析');
      navigate(`/analyses/${res.id}`);
    } catch {
      message.error('重试失败');
    }
  };

  const filtered = analyses.filter((a) => {
    const matchesStatus = statusFilter === 'all' || a.status === statusFilter;
    const matchesSearch =
      !searchText ||
      a.requirement_name?.toLowerCase().includes(searchText.toLowerCase()) ||
      a.project_name?.toLowerCase().includes(searchText.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const columns = [
    {
      title: '需求名称',
      dataIndex: 'requirement_name',
      key: 'requirement_name',
      ellipsis: true,
      render: (v: string) => <span style={{ color: '#e2e8f0' }}>{v || '-'}</span>,
    },
    {
      title: '项目',
      dataIndex: 'project_name',
      key: 'project_name',
      render: (v: string) => <Tag>{v || '-'}</Tag>,
      width: 120,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={STATUS_COLORS[status] || 'default'}>
          {STATUS_LABELS[status] || status}
        </Tag>
      ),
      width: 100,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
      width: 170,
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: AnalysisTask) => (
        <Space>
          {record.status === 'completed' && (
            <Button
              type="primary"
              size="small"
              onClick={() => navigate(`/reports/${record.id}`)}
            >
              查看报告
            </Button>
          )}
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
      width: 180,
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
          placeholder="搜索需求名称或项目..."
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
          <Select.Option value="all">全部状态</Select.Option>
          <Select.Option value="pending">等待中</Select.Option>
          <Select.Option value="running">运行中</Select.Option>
          <Select.Option value="completed">已完成</Select.Option>
          <Select.Option value="failed">失败</Select.Option>
          <Select.Option value="cancelled">已取消</Select.Option>
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
