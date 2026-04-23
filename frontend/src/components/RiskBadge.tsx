import { Tag } from 'antd';
import type { RiskLevel } from '@/types/api';

interface RiskBadgeProps {
  level?: RiskLevel;
  score?: number;
  showScore?: boolean;
}

const RISK_CONFIG: Record<RiskLevel, { color: string; label: string }> = {
  low: { color: 'success', label: '低' },
  medium: { color: 'warning', label: '中' },
  high: { color: 'orange', label: '高' },
  critical: { color: 'error', label: '严重' },
};

export function RiskBadge({ level, score, showScore = false }: RiskBadgeProps) {
  if (!level) {
    return <Tag>未知</Tag>;
  }

  const config = RISK_CONFIG[level];
  const label = showScore && score !== undefined ? `${config.label} (${score})` : config.label;

  return <Tag color={config.color}>{label}</Tag>;
}