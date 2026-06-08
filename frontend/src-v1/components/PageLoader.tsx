import { Spin } from 'antd';

export default function PageLoader() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <Spin size="large" tip="Loading..." />
    </div>
  );
}
