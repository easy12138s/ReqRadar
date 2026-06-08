import { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { App as AntApp } from 'antd';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import AppShell from './components/AppShell';
import ErrorBoundary from './components/ErrorBoundary';
import PageLoader from './components/PageLoader';
import { setNavigate } from './api/client';

const Login = lazy(() => import('./pages/Login').then(m => ({ default: m.Login })));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Projects = lazy(() => import('./pages/Projects').then(m => ({ default: m.Projects })));
const ProjectDetail = lazy(() => import('./pages/ProjectDetail').then(m => ({ default: m.ProjectDetail })));
const ProjectProfile = lazy(() => import('./pages/ProjectProfile').then(m => ({ default: m.ProjectProfile })));
const SynonymManager = lazy(() => import('./pages/SynonymManager').then(m => ({ default: m.SynonymManager })));
const AnalysisList = lazy(() => import('./pages/AnalysisList').then(m => ({ default: m.AnalysisList })));
const AnalysisSubmit = lazy(() => import('./pages/AnalysisSubmit').then(m => ({ default: m.AnalysisSubmit })));
const AnalysisProgress = lazy(() => import('./pages/AnalysisProgress').then(m => ({ default: m.AnalysisProgress })));
const ReportView = lazy(() => import('./pages/ReportView').then(m => ({ default: m.ReportView })));
const LLMConfig = lazy(() => import('./pages/LLMConfig').then(m => ({ default: m.LLMConfig })));
const TemplateManager = lazy(() => import('./pages/TemplateManager').then(m => ({ default: m.TemplateManager })));
const UserPreferences = lazy(() => import('./pages/UserPreferences').then(m => ({ default: m.UserPreferences })));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const UserManagement = lazy(() => import('./pages/UserManagement'));
const RequirementEdit = lazy(() => import('./pages/RequirementEdit'));
const MCPSettings = lazy(() => import('./pages/MCPSettings').then(m => ({ default: m.MCPSettings })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false, // 避免频繁请求
      retry: 1,
      staleTime: 1000 * 60 * 5, // 5 分钟数据不过期
    },
  },
});

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <PageLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <PageLoader />;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function RouteSync() {
  const navigate = useNavigate();
  useEffect(() => { setNavigate(navigate); }, [navigate]);
  return null;
}

function LocationErrorBoundary({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  return <ErrorBoundary key={location.pathname}>{children}</ErrorBoundary>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AntApp>
          <AuthProvider>
            <BrowserRouter basename="/app">
              <RouteSync />
            <Suspense fallback={<PageLoader />}>
              <LocationErrorBoundary>
                <Routes>
                  <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />

                  <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
                    <Route index element={<Dashboard />} />
                    <Route path="projects" element={<Projects />} />
                    <Route path="projects/:id" element={<ProjectDetail />} />
                    <Route path="projects/:id/profile" element={<ProjectProfile />} />
                    <Route path="projects/:id/synonyms" element={<SynonymManager />} />
                    <Route path="analyses" element={<AnalysisList />} />
                    <Route path="analyses/submit" element={<AnalysisSubmit />} />
                    <Route path="analyses/:id" element={<AnalysisProgress />} />
                    <Route path="reports/:taskId" element={<ReportView />} />
                    <Route path="settings" element={<SettingsPage />} />
                    <Route path="settings/llm" element={<LLMConfig />} />
                    <Route path="settings/templates" element={<TemplateManager />} />
                    <Route path="settings/preferences" element={<UserPreferences />} />
                    <Route path="settings/users" element={<UserManagement />} />
      <Route path="settings/mcp" element={<MCPSettings />} />
                    <Route path="requirements/:id" element={<RequirementEdit />} />
                  </Route>

                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </LocationErrorBoundary>
              </Suspense>
            </BrowserRouter>
          </AuthProvider>
        </AntApp>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
