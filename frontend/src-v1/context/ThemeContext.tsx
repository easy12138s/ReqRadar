import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { ConfigProvider, theme as antTheme } from 'antd';
import zhCN from 'antd/locale/zh_CN';

export type ThemeMode = 'light' | 'dark';

interface ThemeContextType {
  themeMode: ThemeMode;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const darkThemeConfig = {
  algorithm: antTheme.darkAlgorithm,
  token: {
    colorPrimary: '#00b8d4',
    colorBgBase: '#0a0a0a',
    colorBgContainer: '#141414',
    colorBgElevated: '#1f1f1f',
    colorBorder: '#262626',
    colorBorderSecondary: '#1f1f1f',
    colorText: '#e5e5e5',
    colorTextSecondary: '#a3a3a3',
    borderRadius: 12,
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif",
  },
  components: {
    Layout: {
      headerBg: 'transparent',
      bodyBg: '#0a0a0a',
      siderBg: '#0a0a0a',
    },
    Card: {
      colorBgContainer: '#141414',
      borderRadiusLG: 16,
      colorBorderSecondary: '#262626',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(0,184,212,0.1)',
    },
    Table: {
      colorBgContainer: '#141414',
      borderColor: '#262626',
      headerBg: '#1f1f1f',
      rowHoverBg: 'rgba(0,184,212,0.04)',
      headerBorderRadius: 12,
    },
    Input: {
      colorBgContainer: '#141414',
      activeBorderColor: '#00b8d4',
      hoverBorderColor: '#00b8d4',
      paddingBlock: 8,
      paddingInline: 12,
    },
    Select: {
      colorBgContainer: '#141414',
      optionSelectedBg: 'rgba(0,184,212,0.1)',
      colorBgElevated: '#1f1f1f',
    },
    Tag: {
      defaultBg: 'rgba(0,184,212,0.08)',
      defaultColor: '#00b8d4',
      borderRadiusSM: 6,
    },
    Button: {
      primaryShadow: '0 4px 14px 0 rgba(0,184,212,0.2)',
      controlHeight: 36,
      borderRadius: 8,
    },
    Tabs: {
      inkBarColor: '#00b8d4',
      itemActiveColor: '#00b8d4',
      itemSelectedColor: '#00b8d4',
      itemHoverColor: '#00b8d4',
    },
  },
};

const lightThemeConfig = {
  algorithm: antTheme.defaultAlgorithm,
  token: {
    colorPrimary: '#00b8d4',
    colorBgBase: '#f8fafc',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorBorder: '#e2e8f0',
    colorBorderSecondary: '#f1f5f9',
    colorText: '#0f172a',
    colorTextSecondary: '#64748b',
    borderRadius: 12,
    fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif",
  },
  components: {
    Layout: {
      headerBg: 'transparent',
      bodyBg: '#f8fafc',
      siderBg: '#f8fafc',
    },
    Card: {
      colorBgContainer: '#ffffff',
      borderRadiusLG: 16,
      colorBorderSecondary: '#e2e8f0',
    },
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: 'rgba(0,184,212,0.08)',
    },
    Table: {
      colorBgContainer: '#ffffff',
      borderColor: '#e2e8f0',
      headerBg: '#f8fafc',
      rowHoverBg: 'rgba(0,184,212,0.03)',
      headerBorderRadius: 12,
    },
    Input: {
      colorBgContainer: '#ffffff',
      activeBorderColor: '#00b8d4',
      hoverBorderColor: '#00b8d4',
      paddingBlock: 8,
      paddingInline: 12,
    },
    Select: {
      colorBgContainer: '#ffffff',
      optionSelectedBg: 'rgba(0,184,212,0.08)',
      colorBgElevated: '#ffffff',
    },
    Tag: {
      defaultBg: 'rgba(0,184,212,0.08)',
      defaultColor: '#00b8d4',
      borderRadiusSM: 6,
    },
    Button: {
      primaryShadow: '0 4px 14px 0 rgba(0,184,212,0.15)',
      controlHeight: 36,
      borderRadius: 8,
    },
    Tabs: {
      inkBarColor: '#00b8d4',
      itemActiveColor: '#00b8d4',
      itemSelectedColor: '#00b8d4',
      itemHoverColor: '#00b8d4',
    },
  },
};

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('app-theme');
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    localStorage.setItem('app-theme', themeMode);
    const root = document.documentElement;
    if (themeMode === 'dark') {
      root.classList.add('dark-theme');
      root.classList.remove('light-theme');
    } else {
      root.classList.add('light-theme');
      root.classList.remove('dark-theme');
    }
  }, [themeMode]);

  const toggleTheme = () => {
    setThemeMode(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  return (
    <ThemeContext.Provider value={{ themeMode, toggleTheme }}>
      <ConfigProvider theme={themeMode === 'dark' ? darkThemeConfig : lightThemeConfig} locale={zhCN}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}

export const useThemeContext = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useThemeContext must be used within a ThemeProvider');
  }
  return context;
};
