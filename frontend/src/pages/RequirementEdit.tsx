import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Button, Input, Typography, Spin, message, Modal, Select, Space } from 'antd';
import { ArrowLeftOutlined, SaveOutlined, CheckCircleOutlined, EditOutlined } from '@ant-design/icons';
import { getRequirement, updateRequirement } from '../api/requirements';
import { createAnalysis } from '../api/analyses';

const { Title } = Typography;
const { TextArea } = Input;

export default function RequirementEdit() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [editingTitle, setEditingTitle] = useState(false);
  const [analysisModalOpen, setAnalysisModalOpen] = useState(false);
  const [analysisDepth, setAnalysisDepth] = useState('standard');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const doc = await getRequirement(Number(id));
        setTitle(doc.title);
        setText(doc.consolidated_text);
      } catch {
        message.error('加载需求文档失败');
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateRequirement(Number(id), text);
      message.success('已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleSubmitAnalysis = async () => {
    setSubmitting(true);
    try {
      const task = await createAnalysis({
        project_id: '',
        requirement_document_id: Number(id),
        depth: analysisDepth as any,
      });
      message.success('分析已提交');
      navigate(`/analyses/${task.id}`);
    } catch {
      message.error('提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>返回</Button>
        {editingTitle ? (
          <Input
            value={title}
            onChange={e => setTitle(e.target.value)}
            onBlur={() => setEditingTitle(false)}
            onPressEnter={() => setEditingTitle(false)}
            style={{ fontSize: 20, fontWeight: 700, width: 400 }}
            autoFocus
          />
        ) : (
          <Title level={3} style={{ margin: 0, cursor: 'pointer' }} onClick={() => setEditingTitle(true)}>
            {title} <EditOutlined style={{ fontSize: 14, opacity: 0.4 }} />
          </Title>
        )}
      </div>

      <Card
        className="glass-card"
        style={{ marginBottom: 24 }}
      >
        <TextArea
          value={text}
          onChange={e => setText(e.target.value)}
          style={{
            minHeight: '60vh',
            fontFamily: 'monospace',
            fontSize: 14,
            lineHeight: 1.8,
            background: 'transparent',
            border: 'none',
            resize: 'none',
          }}
        />
      </Card>

      <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
        <Button
          icon={<SaveOutlined />}
          loading={saving}
          onClick={handleSave}
        >
          保存草稿
        </Button>
        <Button
          type="primary"
          icon={<CheckCircleOutlined />}
          onClick={() => setAnalysisModalOpen(true)}
        >
          确认并提交分析
        </Button>
      </div>

      <Modal
        title="提交需求分析"
        open={analysisModalOpen}
        onCancel={() => setAnalysisModalOpen(false)}
        onOk={handleSubmitAnalysis}
        confirmLoading={submitting}
        okText="开始分析"
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <div style={{ marginBottom: 4, color: '#8b949e', fontSize: 13 }}>分析深度</div>
            <Select
              value={analysisDepth}
              onChange={setAnalysisDepth}
              style={{ width: '100%' }}
              options={[
                { label: '快速 (quick)', value: 'quick' },
                { label: '标准 (standard)', value: 'standard' },
                { label: '深度 (deep)', value: 'deep' },
              ]}
            />
          </div>
        </Space>
      </Modal>
    </div>
  );
}
