import { Select } from 'antd';

const FOCUS_AREAS = [
  '功能完整性',
  '性能',
  '安全性',
  '可维护性',
  '可扩展性',
  '用户体验',
  '兼容性',
  '合规性',
];

interface FocusAreaSelectorProps {
  value?: string[];
  onChange?: (value: string[]) => void;
}

export function FocusAreaSelector({ value, onChange }: FocusAreaSelectorProps) {
  return (
    <Select
      mode="multiple"
      placeholder="选择关注领域"
      value={value}
      onChange={onChange}
      style={{ width: '100%' }}
      allowClear
    >
      {FOCUS_AREAS.map((area) => (
        <Select.Option key={area} value={area}>
          {area}
        </Select.Option>
      ))}
    </Select>
  );
}
