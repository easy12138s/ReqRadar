import { Card, Button, Space, Tag, Typography } from 'antd';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import type { PendingChange } from '@/types/api';

interface PendingChangeCardProps {
  change: PendingChange;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
}

export function PendingChangeCard({ change, onAccept, onReject }: PendingChangeCardProps) {
  return (
    <Card size="small" style={{ marginBottom: 8 }} actions={[
      <Button key="accept" type="link" icon={<CheckOutlined />} onClick={() => onAccept(change.id)}>接受</Button>,
      <Button key="reject" type="link" danger icon={<CloseOutlined />} onClick={() => onReject(change.id)}>拒绝</Button>,
    ]}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space>
          <Tag color={change.type === 'profile' ? 'blue' : 'green'}>{change.type === 'profile' ? '画像' : '同义词'}</Tag>
          <Typography.Text type="secondary">{new Date(change.created_at).toLocaleString()}</Typography.Text>
        </Space>
        <Typography.Paragraph>{change.description}</Typography.Paragraph>
        {change.old_value && change.new_value && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Typography.Text type="secondary" delete style={{ fontSize: 12 }}>{change.old_value.slice(0, 200)}</Typography.Text>
            <Typography.Text type="success" style={{ fontSize: 12 }}>{change.new_value.slice(0, 200)}</Typography.Text>
          </Space>
        )}
      </Space>
    </Card>
  );
}
