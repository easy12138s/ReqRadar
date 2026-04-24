import { useEffect, useState } from 'react';
import { Select, message } from 'antd';
import { getTemplates } from '@/api/templates';
import type { ReportTemplate } from '@/types/api';

interface TemplateSelectorProps {
  value?: string;
  onChange?: (value: string) => void;
}

export function TemplateSelector({ value, onChange }: TemplateSelectorProps) {
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchTemplates = async () => {
      setLoading(true);
      try {
        const data = await getTemplates();
        setTemplates(data);
      } catch {
        message.error('加载模板列表失败');
      } finally {
        setLoading(false);
      }
    };
    fetchTemplates();
  }, []);

  return (
    <Select
      placeholder="选择报告模板"
      value={value}
      onChange={onChange}
      style={{ width: '100%' }}
      loading={loading}
      allowClear
    >
      {templates.map((t) => (
        <Select.Option key={t.id} value={t.id}>
          {t.name}
        </Select.Option>
      ))}
    </Select>
  );
}
