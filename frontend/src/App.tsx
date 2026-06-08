import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import AuthGuard from '@/components/AuthGuard';
import AppLayout from '@/components/AppLayout';

const LoginPage = lazy(() => import('@/pages/LoginPage'));
const DashboardPage = lazy(() => import('@/pages/DashboardPage'));
const AnalysisCreatePage = lazy(() => import('@/pages/AnalysisCreatePage'));
const SessionDetailPage = lazy(() => import('@/pages/SessionDetailPage'));
const SessionEventsPage = lazy(() => import('@/pages/SessionEventsPage'));
const ReportPage = lazy(() => import('@/pages/ReportPage'));
const KnowledgeDashboard = lazy(() => import('@/pages/KnowledgeDashboard'));
const CheckpointsPage = lazy(() => import('@/pages/CheckpointsPage'));

const PageSpinner = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
    <Spin size="large" />
  </div>
);

export default function App() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <AuthGuard>
              <AppLayout>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/analysis/new" element={<AnalysisCreatePage />} />
                  <Route path="/sessions/:sessionId" element={<SessionDetailPage />} />
                  <Route path="/sessions/:sessionId/events" element={<SessionEventsPage />} />
                  <Route path="/sessions/:sessionId/report" element={<ReportPage />} />
                  <Route path="/sessions/:sessionId/checkpoints" element={<CheckpointsPage />} />
                  <Route path="/knowledge/:projectId" element={<KnowledgeDashboard />} />
                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </Routes>
              </AppLayout>
            </AuthGuard>
          }
        />
      </Routes>
    </Suspense>
  );
}
