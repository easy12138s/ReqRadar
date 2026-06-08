import { Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import { AuthProvider, useAuth } from '@/context/AuthContext';

function AuthGuardInner({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <AuthGuardInner>{children}</AuthGuardInner>
    </AuthProvider>
  );
}
