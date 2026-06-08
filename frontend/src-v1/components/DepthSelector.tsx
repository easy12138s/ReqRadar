import { Select } from 'antd';
import type { AnalysisDepth } from '@/types/api';

interface DepthSelectorProps {
  value?: AnalysisDepth;
  onChange?: (value: AnalysisDepth) => void;
}

export function DepthSelector({ value, onChange }: DepthSelectorProps) {
  return (
    <Select<AnalysisDepth>
      placeholder="选择分析深度"
      value={value}
      onChange={onChange}
      style={{ width: '100%' }}
    >
      <Select.Option value="quick">快速</Select.Option>
      <Select.Option value="standard">标准</Select.Option>
      <Select.Option value="deep">深度</Select.Option>
    </Select>
  );
}
