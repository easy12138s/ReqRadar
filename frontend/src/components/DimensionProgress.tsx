import { Progress, Tag, Space } from 'antd';

interface DimensionProgressProps {
  dimensions: Record<string, string>;
  evidenceCount: number;
  step: number;
  maxSteps: number;
}

export function DimensionProgress({ dimensions, evidenceCount, step, maxSteps }: DimensionProgressProps) {
  const percent = maxSteps > 0 ? Math.round((step / maxSteps) * 100) : 0;

  return (
    <div>
      <Progress percent={percent} status="active" />
      <div style={{ marginBottom: 8 }}>
        <span>证据数: {evidenceCount}</span>
      </div>
      <Space wrap>
        {Object.entries(dimensions).map(([key, value]) => (
          <Tag key={key} color={value === 'completed' ? 'success' : value === 'in_progress' ? 'processing' : 'default'}>
            {key}: {value}
          </Tag>
        ))}
      </Space>
    </div>
  );
}
