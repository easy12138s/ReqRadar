import { Tag } from 'antd';
import type { RiskLevel } from '@/types/api';

interface RiskBadgeProps {
  level?: RiskLevel;
  score?: number;
  showScore?: boolean;
}

const RISK_CONFIG: Record<RiskLevel, { color: string; label: string }> = {
  low: { color: 'success', label: 'Low' },
  medium: { color: 'warning', label: 'Medium' },
  high: { color: 'orange', label: 'High' },
  critical: { color: 'error', label: 'Critical' },
};

export function RiskBadge({ level, score, showScore = false }: RiskBadgeProps) {
  if (!level) {
    return <Tag>Unknown</Tag>;
  }

  const config = RISK_CONFIG[level];
  const label = showScore && score !== undefined ? `${config.label} (${score})` : config.label;

  return <Tag color={config.color}>{label}</Tag>;
}
