import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card, message, Spin, Empty, Typography, Tabs, Descriptions, Tag,
} from 'antd';
import {
  getProjectProfile,
  getPendingChanges, acceptPendingChange, rejectPendingChange,
} from '@/api/profile';
import { PendingChangeCard } from '@/components/PendingChangeCard';
import ReactMarkdown from 'react-markdown';
import type { ProjectProfile, PendingChange } from '@/types/api';

const { Title, Text } = Typography;

export function ProjectProfile() {
  const { id: projectId } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<ProjectProfile | null>(null);
  const [pendingChanges, setPendingChanges] = useState<PendingChange[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadData() {
    if (!projectId) return;
    setLoading(true);
    try {
      const [p, c] = await Promise.all([
        getProjectProfile(projectId),
        getPendingChanges(projectId),
      ]);
      setProfile(p);
      setPendingChanges(c.filter(x => x.status === 'pending'));
    } catch { message.error('加载失败'); }
    finally { setLoading(false); }
  }

  useEffect(() => { loadData(); }, [projectId]);

  const handleAccept = async (id: string) => {
    if (!projectId) return;
    try { await acceptPendingChange(projectId, id); message.success('已接受'); loadData(); }
    catch { message.error('操作失败'); }
  };
  const handleReject = async (id: string) => {
    if (!projectId) return;
    try { await rejectPendingChange(projectId, id); message.success('已拒绝'); loadData(); }
    catch { message.error('操作失败'); }
  };

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: 64 }}><Spin size="large" /></div>;

  const d = profile?.data;

  return (
    <div>
      <Title level={3}>项目画像</Title>
      <Tabs
        items={[
          {
            key: 'view',
            label: '当前画像',
            children: d ? (
              <Card>
                <Descriptions column={2} size="small" style={{ marginBottom: 16 }}>
                  <Descriptions.Item label="项目名称">{d.name || '-'}</Descriptions.Item>
                  <Descriptions.Item label="模块">{d.modules?.length || 0} 个</Descriptions.Item>
                  <Descriptions.Item label="术语">{d.terms?.length || 0} 个</Descriptions.Item>
                  <Descriptions.Item label="约束">{d.constraints?.length || 0} 个</Descriptions.Item>
                </Descriptions>

                {d.overview ? (
                  <Card type="inner" title="项目概述" size="small" style={{ marginBottom: 16 }}>
                    <Text style={{ whiteSpace: 'pre-wrap', color: '#c9d1d9' }}>{d.overview}</Text>
                  </Card>
                ) : null}

                {d.tech_stack && Object.keys(d.tech_stack).length > 0 ? (
                  <Card type="inner" title="技术栈" size="small" style={{ marginBottom: 16 }}>
                    {Object.entries(d.tech_stack).map(([cat, items]) => (
                      <div key={cat} style={{ marginBottom: 8 }}>
                        <Text strong>{cat}: </Text>
                        {items.map(item => <Tag key={item} color="blue">{item}</Tag>)}
                      </div>
                    ))}
                  </Card>
                ) : null}

                {d.modules && d.modules.length > 0 ? (
                  <Card type="inner" title={'模块 (' + d.modules.length + ')'} size="small" style={{ marginBottom: 16 }}>
                    {d.modules.map((m, i) => (
                      <div key={i} style={{ marginBottom: 8, padding: '8px 12px', background: 'rgba(0,0,0,0.15)', borderRadius: 8 }}>
                        <Text strong style={{ color: '#e2e8f0' }}>{m.name}</Text>
                        {m.responsibility ? <div style={{ color: '#94a3b8', fontSize: 13 }}>{m.responsibility}</div> : null}
                      </div>
                    ))}
                  </Card>
                ) : null}

                {d.terms && d.terms.length > 0 ? (
                  <Card type="inner" title={'术语 (' + d.terms.length + ')'} size="small">
                    {d.terms.map((t, i) => (
                      <div key={i} style={{ marginBottom: 6, fontSize: 13 }}>
                        <Text strong>{t.term}</Text>: <Text type="secondary">{t.definition}</Text>
                      </div>
                    ))}
                  </Card>
                ) : null}

                {profile?.content ? (
                  <Card type="inner" title="Markdown 原文" size="small" style={{ marginTop: 16 }}>
                    <div className="markdown-body" style={{ maxHeight: 400, overflow: 'auto' }}>
                      <ReactMarkdown>{profile.content}</ReactMarkdown>
                    </div>
                  </Card>
                ) : null}
              </Card>
            ) : <Empty description="暂无画像数据" />,
          },
          {
            key: 'pending',
            label: '待确认变更 (' + pendingChanges.length + ')',
            children: (
              <Card>
                {pendingChanges.length === 0
                  ? <Empty description="暂无待确认变更" />
                  : pendingChanges.map(c => (
                    <PendingChangeCard key={c.id} change={c} onAccept={handleAccept} onReject={handleReject} />
                  ))}
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}
