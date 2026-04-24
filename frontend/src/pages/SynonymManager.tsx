import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Table, Button, Modal, Form, Input, InputNumber, Space, Popconfirm, message, Tag, Spin, Empty } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { getSynonyms, createSynonym, updateSynonym, deleteSynonym } from '@/api/synonyms';
import type { SynonymMapping } from '@/types/api';

export function SynonymManager() {
  const { id: projectId } = useParams<{ id: string }>();
  const [synonyms, setSynonyms] = useState<SynonymMapping[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<SynonymMapping | null>(null);
  const [form] = Form.useForm();
  const [searchTerm, setSearchTerm] = useState('');

  async function loadSynonyms() {
    setLoading(true);
    try {
      const data = await getSynonyms(projectId);
      setSynonyms(data);
    } catch {
      message.error('加载同义词失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadSynonyms(); }, [projectId]);

  const filteredSynonyms = synonyms.filter(
    (s) => s.business_term.toLowerCase().includes(searchTerm.toLowerCase()) ||
           s.code_terms.some((t) => t.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const handleSave = async (values: { business_term: string; code_terms: string; priority: number }) => {
    try {
      const codeTerms = values.code_terms.split(/[,，\n]/).map((t) => t.trim()).filter(Boolean);
      const data = { project_id: projectId, business_term: values.business_term, code_terms: codeTerms, priority: values.priority };
      if (editingRecord) {
        await updateSynonym(editingRecord.id, data);
        message.success('更新成功');
      } else {
        await createSynonym(data);
        message.success('创建成功');
      }
      setModalVisible(false);
      form.resetFields();
      setEditingRecord(null);
      loadSynonyms();
    } catch {
      message.error('保存失败');
    }
  };

  const handleDelete = async (id: string) => {
    try { await deleteSynonym(id); message.success('删除成功'); loadSynonyms(); }
    catch { message.error('删除失败'); }
  };

  const columns = [
    { title: '业务术语', dataIndex: 'business_term', key: 'business_term' },
    { title: '代码术语', dataIndex: 'code_terms', key: 'code_terms', render: (terms: string[]) => <Space wrap>{terms.map((t) => <Tag key={t}>{t}</Tag>)}</Space> },
    { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
    { title: '来源', dataIndex: 'source', key: 'source' },
    { title: '操作', key: 'action', width: 120, render: (_: unknown, record: SynonymMapping) => (
      <Space>
        <Button icon={<EditOutlined />} size="small" onClick={() => { setEditingRecord(record); form.setFieldsValue({ business_term: record.business_term, code_terms: record.code_terms.join(', '), priority: record.priority }); setModalVisible(true); }} />
        <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record.id)}>
          <Button icon={<DeleteOutlined />} size="small" danger />
        </Popconfirm>
      </Space>
    )},
  ];

  return (
    <Card title="同义词映射管理" extra={
      <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingRecord(null); form.resetFields(); setModalVisible(true); }}>新增映射</Button>
    }>
      <Input.Search placeholder="搜索业务术语或代码术语" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} style={{ marginBottom: 16, maxWidth: 400 }} />
      {loading ? <Spin /> : filteredSynonyms.length === 0 ? <Empty description="暂无同义词映射" /> :
        <Table dataSource={filteredSynonyms} columns={columns} rowKey="id" pagination={{ pageSize: 10 }} />}
      <Modal title={editingRecord ? '编辑映射' : '新增映射'} open={modalVisible} onCancel={() => { setModalVisible(false); form.resetFields(); setEditingRecord(null); }} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item name="business_term" label="业务术语" rules={[{ required: true, message: '请输入业务术语' }]}>
            <Input placeholder="例如：用户认证" />
          </Form.Item>
          <Form.Item name="code_terms" label="代码术语" rules={[{ required: true, message: '请输入代码术语' }]} extra="多个术语用逗号或换行分隔">
            <Input.TextArea rows={3} placeholder="例如：auth, authentication, login" />
          </Form.Item>
          <Form.Item name="priority" label="优先级" initialValue={1}>
            <InputNumber min={0} max={10} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
