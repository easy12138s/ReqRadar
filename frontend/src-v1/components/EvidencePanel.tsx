import { useEffect, useState } from 'react';
import { List, Tag, Spin, Empty, message } from 'antd';
import { getEvidenceChain } from '@/api/evidence';
import type { EvidenceItem } from '@/types/api';

interface EvidencePanelProps {
  taskId: string;
  versionNumber?: number;
}

export function EvidencePanel({ taskId, versionNumber }: EvidencePanelProps) {
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchEvidence = async () => {
      setLoading(true);
      try {
        const data = await getEvidenceChain(taskId, versionNumber);
        setEvidence(data.evidence);
      } catch {
        message.error('加载证据链失败');
      } finally {
        setLoading(false);
      }
    };
    fetchEvidence();
  }, [taskId, versionNumber]);

  if (loading) return <Spin size="small" />;
  if (evidence.length === 0) return <Empty description="暂无证据" image={Empty.PRESENTED_IMAGE_SIMPLE} />;

  return (
    <List
      size="small"
      dataSource={evidence}
      renderItem={(item) => (
        <List.Item>
          <div>
            <div>
              <Tag color="blue">{item.type}</Tag>
              <Tag color="green">{item.confidence}</Tag>
              <span style={{ marginLeft: 8, fontSize: 12, color: '#888' }}>{item.source}</span>
            </div>
            <div style={{ marginTop: 4 }}>{item.content}</div>
            <div style={{ marginTop: 4 }}>
              {item.dimensions.map((dim) => (
                <Tag key={dim}>{dim}</Tag>
              ))}
            </div>
          </div>
        </List.Item>
      )}
    />
  );
}
