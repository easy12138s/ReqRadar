import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card, message, Spin, Empty, Typography, Tabs, Descriptions, Tag,
  Form, Input, Button, Divider, Space, theme,
} from 'antd';
import {
  getProjectProfile, updateProjectProfile,
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
  const [editOverview, setEditOverview] = useState('');
  const [editing, setEditing] = useState(false);
  const { token } = theme.useToken();

  async function fetchProfile() {
    if (!projectId) return;
    setLoading(true);
    try {
      const [p, c] = await Promise.all([
        getProjectProfile(projectId),
        getPendingChanges(projectId),
      ]);
      setProfile(p);
      setPendingChanges(c.filter(x => x.status === 'pending'));
      setEditOverview(p?.data?.overview || '');
    } catch { message.error('加载失败'); }
    finally { setLoading(false); }
  }

  useEffect(() => { fetchProfile(); }, [projectId]);

  const handleSave = async () => {
    if (!projectId) return;
    setEditing(true);
    try {
      await updateProjectProfile(projectId, {
        data: { ...(profile?.data || {}), overview: editOverview },
      });
      message.success('Profile updated');
      fetchProfile();
    } catch { message.error('Failed to update profile'); }
    setEditing(false);
  };

  const handleAccept = async (id: string) => {
    if (!projectId) return;
    try { await acceptPendingChange(projectId, id); message.success('已接受'); fetchProfile(); }
    catch { message.error('操作失败'); }
  };
  const handleReject = async (id: string) => {
    if (!projectId) return;
    try { await rejectPendingChange(projectId, id); message.success('已拒绝'); fetchProfile(); }
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
              <div style={{ maxWidth: 860 }}>
                <Title level={5}>项目概述</Title>
                <div style={{ whiteSpace: 'pre-wrap', color: token.colorText }}>{d.overview || '暂无'}</div>

                <Divider />

                <Title level={5}>技术栈</Title>
                {d.tech_stack && Object.keys(d.tech_stack).length > 0
                  ? Object.entries(d.tech_stack).map(([cat, items]) => (
                    <div key={cat} style={{ marginBottom: 12 }}>
                      <Text strong>{cat}:</Text>
                      <Space wrap style={{ marginLeft: 8 }}>
                        {items.map((item: string) => <Tag key={item}>{item}</Tag>)}
                      </Space>
                    </div>
                  ))
                  : <Text type="secondary">暂无</Text>}

                <Divider />

                <Title level={5}>模块</Title>
                {d.modules && d.modules.length > 0
                  ? d.modules.map((m, i) => (
                    <div key={i} style={{ marginBottom: 8, padding: '8px 12px', borderRadius: 8, border: `1px solid ${token.colorBorderSecondary}` }}>
                      <Text strong>{m.name}</Text>
                      {m.responsibility ? <div style={{ color: token.colorTextSecondary, fontSize: 13 }}>{m.responsibility}</div> : null}
                    </div>
                  ))
                  : <Text type="secondary">暂无</Text>}

                <Divider />

                <Title level={5}>术语</Title>
                {d.terms && d.terms.length > 0
                  ? d.terms.map((t, i) => (
                    <div key={i} style={{ marginBottom: 6, fontSize: 13 }}>
                      <Text strong>{t.term}</Text>: <Text type="secondary">{t.definition}</Text>
                    </div>
                  ))
                  : <Text type="secondary">暂无</Text>}

                <Divider />

                <Title level={5}>约束条件</Title>
                {d.constraints && d.constraints.length > 0
                  ? <ul style={{ paddingLeft: 20 }}>
                    {d.constraints.map((c: string, i: number) => <li key={i} style={{ marginBottom: 4 }}>{c}</li>)}
                  </ul>
                  : <Text type="secondary">暂无</Text>}

                {profile?.content ? (
                  <>
                    <Divider />
                    <Title level={5}>Markdown 原文</Title>
                    <div className="markdown-body" style={{ maxHeight: 400, overflow: 'auto' }}>
                      <ReactMarkdown>{profile.content}</ReactMarkdown>
                    </div>
                  </>
                ) : null}
              </div>
            ) : <Empty description="暂无画像数据" />,
          },
          {
            key: 'edit',
            label: '编辑画像',
            children: d ? (
              <Form layout="vertical">
                <Form.Item label="项目名称">
                  <Input value={d.name || ''} disabled />
                </Form.Item>
                <Form.Item label="项目概述">
                  <Input.TextArea
                    value={editOverview}
                    onChange={e => setEditOverview(e.target.value)}
                    rows={6}
                  />
                </Form.Item>
                <Form.Item>
                  <Button type="primary" onClick={handleSave} loading={editing}>
                    保存
                  </Button>
                </Form.Item>
              </Form>
            ) : <Empty description="暂无画像数据" />,
          },
          {
            key: 'pending',
            label: '待确认变更 (' + pendingChanges.length + ')',
            children: (
              pendingChanges.length === 0
                ? <Empty description="暂无待确认变更" />
                : pendingChanges.map(c => (
                  <PendingChangeCard key={c.id} change={c} onAccept={handleAccept} onReject={handleReject} />
                ))
            ),
          },
        ]}
      />
    </div>
  );
}
