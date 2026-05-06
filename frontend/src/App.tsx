import { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme as antTheme, App as AntApp } from 'antd';
import { AuthProvider, useAuth } from './context/AuthContext';
import AppShell from './components/AppShell';
import ErrorBoundary from './components/ErrorBoundary';
import PageLoader from './components/PageLoader';

const Login = lazy(() => import('./pages/Login').then(m => ({ default: m.Login })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
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

const darkTheme = {
  algorithm: antTheme.darkAlgorithm,
  token: {
    colorPrimary: '#00d4ff',
    colorBgBase: '#0a0e17',
    colorBgContainer: '#0f1624',
    colorBgElevated: '#161b22',
    colorBorder: '#1e293b',
    colorBorderSecondary: '#1e293b',
    borderRadius: 8,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif",
  },
  components: {
    Layout: {
      headerBg: 'transparent',
      bodyBg: '#0a0e17',
      siderBg: '#0a0e17',
    },
    Card: {
      colorBgContainer: 'rgba(15,22,36,0.7)',
      borderRadiusLG: 12,
      colorBorderSecondary: '#1e293b',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(0,212,255,0.1)',
    },
    Table: {
      colorBgContainer: '#0f1624',
      borderColor: '#1e293b',
      headerBg: '#1c2535',
      rowHoverBg: 'rgba(0,212,255,0.04)',
    },
    Input: {
      colorBgContainer: '#1c2535',
      activeBorderColor: '#00d4ff',
    },
    Select: {
      colorBgContainer: '#1c2535',
      optionSelectedBg: 'rgba(0,212,255,0.12)',
      colorBgElevated: '#161b22',
    },
    Tag: {
      defaultBg: 'rgba(0,212,255,0.08)',
      defaultColor: '#00d4ff',
    },
    Button: {
      primaryShadow: '0 0 0 2px rgba(0,212,255,0.15)',
    },
    Tabs: {
      inkBarColor: '#00d4ff',
      itemActiveColor: '#00d4ff',
      itemSelectedColor: '#00d4ff',
    },
  },
};

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

export default function App() {
  return (
    <ConfigProvider theme={darkTheme}>
      <AntApp>
        <AuthProvider>
          <BrowserRouter basename="/app">
            <Suspense fallback={<PageLoader />}>
              <ErrorBoundary>
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
                    <Route path="settings/llm" element={<LLMConfig />} />
                    <Route path="settings/templates" element={<TemplateManager />} />
                    <Route path="settings/preferences" element={<UserPreferences />} />
                  </Route>

                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </ErrorBoundary>
            </Suspense>
          </BrowserRouter>
        </AuthProvider>
      </AntApp>
    </ConfigProvider>
  );
}
