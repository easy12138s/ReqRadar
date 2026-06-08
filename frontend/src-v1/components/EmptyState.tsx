import { Button, Typography, theme } from 'antd';
import type { ReactNode } from 'react';

const { Title, Text } = Typography;

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
    icon?: ReactNode;
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
}

/**
 * 自定义空状态组件
 * 提供统一的空状态视觉设计和引导操作
 */
export function EmptyState({ icon, title, description, action, secondaryAction }: EmptyStateProps) {
  const { token } = theme.useToken();

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '80px 24px',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          width: 80,
          height: 80,
          borderRadius: '50%',
          background: `${token.colorPrimary}10`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 24,
          fontSize: 36,
          color: token.colorPrimary,
        }}
      >
        {icon}
      </div>
      <Title
        level={4}
        style={{
          margin: '0 0 8px',
          color: token.colorText,
          fontWeight: 600,
        }}
      >
        {title}
      </Title>
      <Text
        type="secondary"
        style={{
          display: 'block',
          marginBottom: 24,
          maxWidth: 400,
          lineHeight: 1.6,
        }}
      >
        {description}
      </Text>
      <div style={{ display: 'flex', gap: 12 }}>
        {action && (
          <Button
            type="primary"
            size="large"
            icon={action.icon}
            onClick={action.onClick}
          >
            {action.label}
          </Button>
        )}
        {secondaryAction && (
          <Button
            size="large"
            onClick={secondaryAction.onClick}
          >
            {secondaryAction.label}
          </Button>
        )}
      </div>
    </div>
  );
}
