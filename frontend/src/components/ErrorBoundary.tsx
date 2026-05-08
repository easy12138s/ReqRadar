import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button, Result } from 'antd';
import i18n from '../i18n';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <Result
          status="error"
          title={i18n.t('components.error.title')}
          subTitle={import.meta.env.DEV ? this.state.error?.message : undefined}
          extra={
            <Button type="primary" onClick={() => window.location.reload()}>
              {i18n.t('components.error.refresh')}
            </Button>
          }
        />
      );
    }
    return this.props.children;
  }
}
