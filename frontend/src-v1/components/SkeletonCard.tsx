import { Skeleton } from 'antd';

export default function SkeletonCard({ count = 3 }: { count?: number }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={{ padding: 16, background: 'var(--card-bg, #0f1624)', borderRadius: 12, border: '1px solid #1e293b' }}>
          <Skeleton active paragraph={{ rows: 3 }} />
        </div>
      ))}
    </div>
  );
}
