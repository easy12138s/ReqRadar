import { Skeleton } from 'antd';

export default function SkeletonStat({ count = 4 }: { count?: number }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={{ padding: 20, background: 'var(--card-bg, #0f1624)', borderRadius: 12, border: '1px solid #1e293b' }}>
          <Skeleton active paragraph={{ rows: 1 }} title={{ width: '40%' }} />
          <Skeleton.Input active size="large" style={{ marginTop: 8, width: '60%' }} />
        </div>
      ))}
    </div>
  );
}
