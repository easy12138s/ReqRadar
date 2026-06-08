import { Skeleton } from 'antd';

export default function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div style={{ padding: 16, background: 'var(--card-bg, #0f1624)', borderRadius: 12, border: '1px solid #1e293b' }}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} active paragraph={{ rows: 1 }} title={false} style={{ marginBottom: 8 }} />
      ))}
    </div>
  );
}
