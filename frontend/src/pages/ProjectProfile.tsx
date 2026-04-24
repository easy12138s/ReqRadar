import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Input, Button, message, Spin, Empty, Typography, Space, Tabs } from 'antd';
import { getProjectProfile, updateProjectProfile, getPendingChanges, acceptPendingChange, rejectPendingChange } from '@/api/profile';
import { PendingChangeCard } from '@/components/PendingChangeCard';
import type { ProjectProfile as ProjectProfileType, PendingChange } from '@/types/api';

const { TextArea } = Input;
const { Title } = Typography;

export function ProjectProfile() {
  const { id: projectId } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<ProjectProfileType | null>(null);
  const [pendingChanges, setPendingChanges] = useState<PendingChange[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [description, setDescription] = useState('');

  async function loadData() {
    if (!projectId) return;
    setLoading(true);
    try {
      const [profileData, changesData] = await Promise.all([
        getProjectProfile(projectId),
        getPendingChanges(projectId),
      ]);
      setProfile(profileData);
      setDescription(profileData.description || '');
      setPendingChanges(changesData.filter((c) => c.status === 'pending'));
    } catch {
      message.error('加载项目画像失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, [projectId]);

  const handleSave = async () => {
    if (!projectId || !profile) return;
    setSaving(true);
    try {
      await updateProjectProfile(projectId, { ...profile, description });
      message.success('画像已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleAccept = async (changeId: string) => {
    if (!projectId) return;
    try { await acceptPendingChange(projectId, changeId); message.success('已接受'); loadData(); }
    catch { message.error('操作失败'); }
  };

  const handleReject = async (changeId: string) => {
    if (!projectId) return;
    try { await rejectPendingChange(projectId, changeId); message.success('已拒绝'); loadData(); }
    catch { message.error('操作失败'); }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 64 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="large">
      <Title level={3}>项目画像管理</Title>
      <Tabs items={[
        {
          key: 'profile', label: '画像编辑',
          children: (
            <Card>
              <Space direction="vertical" style={{ width: '100%' }}>
                <TextArea value={description} onChange={(e) => setDescription(e.target.value)} rows={10} placeholder="输入项目描述..." />
                <Button type="primary" onClick={handleSave} loading={saving}>保存画像</Button>
              </Space>
            </Card>
          ),
        },
        {
          key: 'pending', label: `待确认变更 (${pendingChanges.length})`,
          children: (
            <Card>
              {pendingChanges.length === 0 ? <Empty description="暂无待确认变更" /> :
                pendingChanges.map((change) => <PendingChangeCard key={change.id} change={change} onAccept={handleAccept} onReject={handleReject} />)}
            </Card>
          ),
        },
      ]} />
    </Space>
  );
}
