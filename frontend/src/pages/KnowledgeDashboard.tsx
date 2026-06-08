import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Tabs, Table, Tag, Typography, Empty, Spin, Progress, Input, Space, Badge } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { getProjectKnowledge } from '@/api/knowledge';
import type { KnowledgeType, FreshnessStatus } from '@/types';

const knowledgeTypeLabels: Record<KnowledgeType, string> = {
  glossary: '术语表',
  module_profile: '模块画像',
  constraint: '架构约束',
  pattern: '代码模式',
  decision: '历史决策',
  risk: '风险记录',
  incident: '事故记录',
  requirement: '需求',
};

const knowledgeTypeColors: Record<KnowledgeType, string> = {
  glossary: 'blue',
  module_profile: 'green',
  constraint: 'red',
  pattern: 'purple',
  decision: 'gold',
  risk: 'orange',
  incident: 'magenta',
  requirement: 'cyan',
};

const freshnessColors: Record<FreshnessStatus, string> = {
  active: 'success',
  historical: 'default',
  superseded: 'warning',
  deprecated: 'default',
  stale: 'warning',
  conflicted: 'error',
};

const freshnessLabels: Record<FreshnessStatus, string> = {
  active: '活跃',
  historical: '历史',
  superseded: '已替代',
  deprecated: '已废弃',
  stale: '过期',
  conflicted: '冲突',
};

const knowledgeColumns = [
  {
    title: '主题',
    dataIndex: 'topic',
    key: 'topic',
    width: 200,
    render: (t: string) => <Typography.Text strong>{t}</Typography.Text>,
  },
  {
    title: '内容摘要',
    dataIndex: 'content',
    key: 'content',
    ellipsis: true,
    render: (c: string) => c?.slice(0, 200),
  },
  {
    title: '置信度',
    dataIndex: 'confidence',
    key: 'confidence',
    width: 100,
    render: (c: number) => <Progress percent={Math.round(c * 100)} size="small" />,
  },
  {
    title: '新鲜度',
    dataIndex: 'freshness',
    key: 'freshness',
    width: 100,
    render: (f: FreshnessStatus) => <Badge status={freshnessColors[f]} text={freshnessLabels[f]} />,
  },
  {
    title: '更新时间',
    dataIndex: 'updated_at',
    key: 'updated_at',
    width: 180,
    render: (t: string) => new Date(t).toLocaleString('zh-CN'),
  },
];

export default function KnowledgeDashboard() {
  const { projectId } = useParams<{ projectId: string }>();
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState('all');

  const { data, isLoading } = useQuery({
    queryKey: ['knowledge', projectId, activeTab],
    queryFn: () => getProjectKnowledge(projectId!, activeTab === 'all' ? undefined : activeTab),
    enabled: !!projectId,
  });

  const items = (data?.items ?? []).filter((e) =>
    !search || e.topic.toLowerCase().includes(search.toLowerCase()) || e.content.toLowerCase().includes(search.toLowerCase()),
  );

  const tabItems = [
    { key: 'all', label: `全部 (${items.length})`, children: null },
    ...Object.entries(knowledgeTypeLabels).map(([key, label]) => {
      const count = items.filter((e) => e.knowledge_type === key).length;
      return { key, label: `${label} (${count})`, children: null };
    }),
  ];

  const displayItems = activeTab === 'all' ? items : items.filter((e) => e.knowledge_type === activeTab);

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4}>知识库</Typography.Title>
        <Space>
          <Input prefix={<SearchOutlined />} placeholder="搜索主题或内容..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ width: 250 }} allowClear />
        </Space>
      </div>

      <Card>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
        {displayItems.length === 0 ? (
          <Empty description="暂无知识条目" />
        ) : (
          <Table dataSource={displayItems} columns={knowledgeColumns} rowKey="knowledge_id" size="small" pagination={{ pageSize: 20 }} />
        )}
      </Card>
    </div>
  );
}
