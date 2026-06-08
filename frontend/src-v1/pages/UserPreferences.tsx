import { useState, useEffect } from 'react';
import { Card, Form, Select, Checkbox, Button, message, Spin } from 'antd';
import { getConfig, setConfig } from '@/api/configs';
import type { AnalysisDepth } from '@/types/api';
import { FOCUS_AREAS } from '@/constants/focusAreas';

const DEPTH_OPTIONS = [
  { label: '快速 (10步)', value: 'quick' },
  { label: '标准 (15步)', value: 'standard' },
  { label: '深度 (25步)', value: 'deep' },
];

export function UserPreferences() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function loadPreferences() {
      try {
        const [depthRes, langRes, focusRes] = await Promise.all([
          getConfig('analysis.default_depth').catch(() => ({ value: 'standard' })),
          getConfig('report.language').catch(() => ({ value: 'zh' })),
          getConfig('analysis.focus_areas').catch(() => ({ value: [] })),
        ]);
        form.setFieldsValue({
          default_depth: depthRes.value as AnalysisDepth,
          report_language: langRes.value as string,
          focus_areas: focusRes.value as string[],
        });
      } catch {
        message.error('加载偏好设置失败');
      } finally {
        setLoading(false);
      }
    }
    loadPreferences();
  }, [form]);

  const handleSave = async (values: { default_depth: AnalysisDepth; report_language: string; focus_areas: string[] }) => {
    setSaving(true);
    try {
      await Promise.all([
        setConfig('analysis.default_depth', values.default_depth),
        setConfig('report.language', values.report_language),
        setConfig('analysis.focus_areas', values.focus_areas),
      ]);
      message.success('偏好设置已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 64 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Card title="用户偏好设置">
      <Form form={form} layout="vertical" onFinish={handleSave} style={{ maxWidth: 600 }}>
        <Form.Item name="default_depth" label="默认分析深度" rules={[{ required: true }]}>
          <Select options={DEPTH_OPTIONS} />
        </Form.Item>
        <Form.Item name="report_language" label="报告语言" rules={[{ required: true }]}>
          <Select options={[{ label: '中文', value: 'zh' }, { label: 'English', value: 'en' }]} />
        </Form.Item>
        <Form.Item name="focus_areas" label="关注领域">
          <Checkbox.Group options={[...FOCUS_AREAS]} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>保存设置</Button>
        </Form.Item>
      </Form>
    </Card>
  );
}
