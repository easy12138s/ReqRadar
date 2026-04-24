import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, Spin } from 'antd';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { AppLayout } from '@/layouts/AppLayout';

const Login = lazy(() => import('@/pages/Login').then(m => ({ default: m.Login })));
const Projects = lazy(() => import('@/pages/Projects').then(m => ({ default: m.Projects })));
const ProjectDetail = lazy(() => import('@/pages/ProjectDetail').then(m => ({ default: m.ProjectDetail })));
const AnalysisSubmit = lazy(() => import('@/pages/AnalysisSubmit').then(m => ({ default: m.AnalysisSubmit })));
const AnalysisList = lazy(() => import('@/pages/AnalysisList').then(m => ({ default: m.AnalysisList })));
const AnalysisProgress = lazy(() => import('@/pages/AnalysisProgress').then(m => ({ default: m.AnalysisProgress })));
const ReportView = lazy(() => import('@/pages/ReportView').then(m => ({ default: m.ReportView })));
const ProjectProfile = lazy(() => import('@/pages/ProjectProfile').then(m => ({ default: m.ProjectProfile })));
const SynonymManager = lazy(() => import('@/pages/SynonymManager').then(m => ({ default: m.SynonymManager })));
const SettingsLayout = lazy(() => import('@/pages/SettingsLayout').then(m => ({ default: m.SettingsLayout })));
const TemplateManager = lazy(() => import('@/pages/TemplateManager').then(m => ({ default: m.TemplateManager })));
const UserPreferences = lazy(() => import('@/pages/UserPreferences').then(m => ({ default: m.UserPreferences })));

function PageLoader() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <Spin size="large" tip="Loading..." />
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return null;
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1677ff',
        },
      }}
    >
      <AuthProvider>
        <BrowserRouter basename="/app">
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route
                path="/login"
                element={
                  <PublicRoute>
                    <Login />
                  </PublicRoute>
                }
              />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="/projects" replace />} />
                <Route path="projects" element={<Projects />} />
                <Route path="projects/:id" element={<ProjectDetail />} />
                <Route path="analyses" element={<AnalysisList />} />
                <Route path="analyses/submit" element={<AnalysisSubmit />} />
                <Route path="analyses/:id" element={<AnalysisProgress />} />
                <Route path="reports/:taskId" element={<ReportView />} />
                <Route path="projects/:id/profile" element={<ProjectProfile />} />
                <Route path="projects/:id/synonyms" element={<SynonymManager />} />
                <Route path="settings" element={<SettingsLayout />}>
                  <Route index element={<Navigate to="/settings/templates" replace />} />
                  <Route path="templates" element={<TemplateManager />} />
                  <Route path="preferences" element={<UserPreferences />} />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ConfigProvider>
  );
}
