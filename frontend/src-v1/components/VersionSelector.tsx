import { useEffect, useState } from 'react';
import { Select, Button, Space, message } from 'antd';
import { RollbackOutlined } from '@ant-design/icons';
import { getVersions, rollbackVersion } from '@/api/versions';
import type { ReportVersion } from '@/types/api';

interface VersionSelectorProps {
  taskId: string;
  currentVersion?: number;
  onVersionChange: (version?: number) => void;
}

export function VersionSelector({ taskId, currentVersion, onVersionChange }: VersionSelectorProps) {
  const [versions, setVersions] = useState<ReportVersion[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchVersions = async () => {
      setLoading(true);
      try {
        const data = await getVersions(taskId);
        setVersions(data.versions);
      } catch {
        message.error('加载版本列表失败');
      } finally {
        setLoading(false);
      }
    };
    fetchVersions();
  }, [taskId]);

  const handleRollback = async () => {
    if (currentVersion === undefined) return;
    try {
      await rollbackVersion(taskId, currentVersion);
      message.success('回滚成功');
    } catch {
      message.error('回滚失败');
    }
  };

  return (
    <Space>
      <Select
        placeholder="选择版本"
        value={currentVersion}
        onChange={(v) => onVersionChange(v)}
        loading={loading}
        style={{ width: 200 }}
        allowClear
      >
        {versions.map((v) => (
          <Select.Option key={v.version_number} value={v.version_number}>
            版本 {v.version_number} - {v.trigger_description}
          </Select.Option>
        ))}
      </Select>
      <Button icon={<RollbackOutlined />} onClick={handleRollback} disabled={currentVersion === undefined}>
        回滚
      </Button>
    </Space>
  );
}
