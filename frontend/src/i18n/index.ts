import { useCallback } from 'react';
import zhCN from './locales/zh-CN';

const _locales: Record<string, typeof zhCN> = {};
let _currentLocale = 'zh-CN';

async function loadLocale(locale: string) {
  if (locale === 'zh-CN') {
    _locales[locale] = zhCN;
  } else {
    const mod = await import(`./locales/${locale}.ts`);
    _locales[locale] = mod.default;
  }
}

export function t(path: string): string {
  const keys = path.split('.');
  let value: unknown = _locales[_currentLocale] || zhCN;
  for (const key of keys) {
    if (value && typeof value === 'object') {
      value = (value as Record<string, unknown>)[key];
    } else {
      return path;
    }
  }
  return typeof value === 'string' ? value : path;
}

export function useTranslation() {
  const translate = useCallback((path: string) => t(path), []);
  return { t: translate };
}

export default loadLocale;
