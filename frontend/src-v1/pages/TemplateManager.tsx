import { useState, useEffect } from 'react';
import { Card, Table, Button, Modal, Form, Input, Space, Popconfirm, message, Tag, Spin, Empty } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, StarOutlined } from '@ant-design/icons';
import { getTemplates, createTemplate, updateTemplate, deleteTemplate, setDefaultTemplate } from '@/api/templates';
import type { ReportTemplate } from '@/types/api';

export function TemplateManager() {
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<ReportTemplate | null>(null);
  const [form] = Form.useForm();

  async function loadTemplates() {
    setLoading(true);
    try { const data = await getTemplates(); setTemplates(data); }
    catch { message.error('加载模板失败'); }
    finally { setLoading(false); }
  }

  useEffect(() => { loadTemplates(); }, []);

  const handleSave = async (values: { name: string; description: string; definition: string; render_template: string }) => {
    try {
      if (editingTemplate) { await updateTemplate(editingTemplate.id, values); message.success('模板已更新'); }
      else { await createTemplate(values); message.success('模板已创建'); }
      setModalVisible(false); form.resetFields(); setEditingTemplate(null); loadTemplates();
    } catch { message.error('保存失败'); }
  };

  const handleDelete = async (id: string) => {
    try { await deleteTemplate(id); message.success('模板已删除'); loadTemplates(); }
    catch { message.error('删除失败'); }
  };

  const handleSetDefault = async (id: string) => {
    try { await setDefaultTemplate(id); message.success('已设为默认模板'); loadTemplates(); }
    catch { message.error('设置失败'); }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '默认', dataIndex: 'is_default', key: 'is_default', width: 80, render: (isDefault: boolean) => isDefault ? <Tag color="blue">默认</Tag> : null },
    { title: '操作', key: 'action', width: 200, render: (_: unknown, record: ReportTemplate) => (
      <Space>
        {!record.is_default && <Button icon={<StarOutlined />} size="small" onClick={() => handleSetDefault(record.id)}>设为默认</Button>}
        <Button icon={<EditOutlined />} size="small" onClick={() => { setEditingTemplate(record); form.setFieldsValue(record); setModalVisible(true); }} />
        <Popconfirm title="确认删除此模板？" onConfirm={() => handleDelete(record.id)}>
          <Button icon={<DeleteOutlined />} size="small" danger />
        </Popconfirm>
      </Space>
    )},
  ];

  return (
    <Card title="报告模板管理" extra={
      <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingTemplate(null); form.resetFields(); setModalVisible(true); }}>新建模板</Button>
    }>
      {loading ? <Spin /> : templates.length === 0 ? <Empty description="暂无模板" /> :
        <Table dataSource={templates} columns={columns} rowKey="id" pagination={{ pageSize: 10 }} />}
      <Modal title={editingTemplate ? '编辑模板' : '新建模板'} open={modalVisible} onCancel={() => { setModalVisible(false); form.resetFields(); setEditingTemplate(null); }} onOk={() => form.submit()} width={800}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="name" label="模板名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="definition" label="模板定义 (YAML)" rules={[{ required: true }]}>
            <Input.TextArea rows={12} placeholder="输入模板定义 YAML..." />
          </Form.Item>
          <Form.Item name="render_template" label="渲染模板" rules={[{ required: true }]}>
            <Input.TextArea rows={12} placeholder="输入 Jinja2 渲染模板..." />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
