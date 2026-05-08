import { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { ConfigProvider, theme as antTheme, App as AntApp } from 'antd';
import { useTranslation } from 'react-i18next';
import zhCN from 'antd/locale/zh_CN';
import enUS from 'antd/locale/en_US';
import { AuthProvider, useAuth } from './context/AuthContext';
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

const darkTheme = {
  algorithm: antTheme.darkAlgorithm,
  token: {
    colorPrimary: '#00b8d4',
    colorBgBase: '#0d1117',
    colorBgContainer: '#1c2333',
    colorBgElevated: '#222b3a',
    colorBorder: '#363b48',
    colorBorderSecondary: '#363b48',
    colorText: '#e6edf3',
    colorTextSecondary: '#8b949e',
    borderRadius: 8,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif",
  },
  components: {
    Layout: {
      headerBg: 'transparent',
      bodyBg: '#0d1117',
      siderBg: '#0d1117',
    },
    Card: {
      colorBgContainer: '#1c2333',
      borderRadiusLG: 12,
      colorBorderSecondary: '#363b48',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(0,184,212,0.15)',
    },
    Table: {
      colorBgContainer: '#1c2333',
      borderColor: '#363b48',
      headerBg: '#222b3a',
      rowHoverBg: 'rgba(0,184,212,0.06)',
    },
    Input: {
      colorBgContainer: '#222b3a',
      activeBorderColor: '#00b8d4',
    },
    Select: {
      colorBgContainer: '#222b3a',
      optionSelectedBg: 'rgba(0,184,212,0.15)',
      colorBgElevated: '#222b3a',
    },
    Tag: {
      defaultBg: 'rgba(0,184,212,0.12)',
      defaultColor: '#00b8d4',
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

function RouteSync() {
  const navigate = useNavigate();
  useEffect(() => { setNavigate(navigate); }, [navigate]);
  return null;
}

function LocaleConfig({ children }: { children: React.ReactNode }) {
  const { i18n } = useTranslation();
  return (
    <ConfigProvider theme={darkTheme} locale={i18n.language === 'zh-CN' ? zhCN : enUS}>
      {children}
    </ConfigProvider>
  );
}

export default function App() {
  return (
    <LocaleConfig>
      <AntApp>
        <AuthProvider>
          <BrowserRouter basename="/app">
            <RouteSync />
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
                    <Route path="settings" element={<SettingsPage />} />
                    <Route path="settings/llm" element={<LLMConfig />} />
                    <Route path="settings/templates" element={<TemplateManager />} />
                    <Route path="settings/preferences" element={<UserPreferences />} />
                    <Route path="settings/users" element={<UserManagement />} />
                    <Route path="requirements/:id" element={<RequirementEdit />} />
                  </Route>

                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </ErrorBoundary>
            </Suspense>
          </BrowserRouter>
        </AuthProvider>
      </AntApp>
    </LocaleConfig>
  );
}
