import { Select } from 'antd';
import { FOCUS_AREAS } from '@/constants/focusAreas';

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
