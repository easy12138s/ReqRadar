import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  Typography,
  Tabs,
  message,
  Empty,
  Spin,
  Upload,
  Space,
} from 'antd';
import { SendOutlined, InboxOutlined } from '@ant-design/icons';
import type { Project, AnalysisDepth } from '@/types/api';
import { getProjects } from '@/api/projects';
import { createAnalysis, uploadAnalysis } from '@/api/analyses';
import { FileUploader } from '@/components/FileUploader';
import { DepthSelector } from '@/components/DepthSelector';
import { TemplateSelector } from '@/components/TemplateSelector';
import { FocusAreaSelector } from '@/components/FocusAreaSelector';
import { preprocessRequirements } from '../api/requirements';

const { Title } = Typography;
const { TextArea } = Input;
const { Option } = Select;

export function AnalysisSubmit() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [depth, setDepth] = useState<AnalysisDepth>('standard');
  const [templateId, setTemplateId] = useState<string | undefined>(undefined);
  const [focusAreas, setFocusAreas] = useState<string[]>([]);
  const [textForm] = Form.useForm();
  const [preprocessFiles, setPreprocessFiles] = useState<File[]>([]);
  const [preprocessing, setPreprocessing] = useState(false);
  const [preprocessTitle, setPreprocessTitle] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const data = await getProjects();
        setProjects(data);
      } catch {
        message.error('加载项目列表失败');
      } finally {
        setLoading(false);
      }
    };
    fetchProjects();
  }, []);

  const handleTextSubmit = async (values: { project_id: number; text: string }) => {
    setSubmitting(true);
    try {
      const task = await createAnalysis({
        project_id: Number(values.project_id),
        text: values.text,
        depth,
        template_id: templateId,
        focus_areas: focusAreas.length > 0 ? focusAreas : undefined,
      });
      message.success('分析任务已提交');
      navigate(`/analyses/${task.id}`);
    } catch (err) {
      console.error('Submit analysis failed:', err);
      message.error('提交分析失败，请检查输入或联系管理员');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    const projectId = textForm.getFieldValue('project_id');
    if (!projectId) {
      message.error('请先选择项目');
      throw new Error('No project selected');
    }
    const task = await uploadAnalysis(
      projectId,
      file,
      depth,
      templateId,
      focusAreas.length > 0 ? focusAreas : undefined,
    );
    message.success('文件上传成功，分析已开始');
    navigate(`/analyses/${task.id}`);
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <Empty description="请先创建项目">
        <Button type="primary" onClick={() => navigate('/projects')}>
          前往项目页
        </Button>
      </Empty>
    );
  }

  const tabItems = [
    {
      key: 'text',
      label: '文本输入',
      children: (
        <Form
          form={textForm}
          onFinish={handleTextSubmit}
          onFinishFailed={(errorInfo) => {
            message.error('请填写必填字段：' + errorInfo.errorFields.map((f: any) => f.name.join('.')).join(', '));
          }}
          layout="vertical"
        >
          <Form.Item
            label="项目"
            name="project_id"
            rules={[{ required: true, message: '请选择项目' }]}
          >
            <Select placeholder="请选择项目">
              {projects.map((p) => (
                <Option key={p.id} value={p.id}>
                  {p.name}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            label="需求文本"
            name="text"
            rules={[{ required: true, message: '请输入需求文本' }]}
          >
            <TextArea
              rows={12}
              placeholder="请将需求文档内容粘贴到此处..."
              showCount
              maxLength={50000}
            />
          </Form.Item>
          <Form.Item label="分析深度">
            <DepthSelector value={depth} onChange={(v) => setDepth(v)} />
          </Form.Item>
          <Form.Item label="报告模板">
            <TemplateSelector value={templateId} onChange={(v) => setTemplateId(v)} />
          </Form.Item>
          <Form.Item label="关注领域">
            <FocusAreaSelector value={focusAreas} onChange={(v) => setFocusAreas(v)} />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={submitting}
              disabled={submitting}
              icon={<SendOutlined />}
            >
              提交分析
            </Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'file',
      label: '文件上传',
      children: (
        <div>
          <Form form={textForm} layout="vertical">
            <Form.Item
              label="项目"
              name="project_id"
              rules={[{ required: true, message: '请选择项目' }]}
            >
              <Select placeholder="请选择项目">
                {projects.map((p) => (
                  <Option key={p.id} value={p.id}>
                    {p.name}
                  </Option>
                ))}
              </Select>
            </Form.Item>
          </Form>
          <FileUploader
            onUpload={handleFileUpload}
            accept=".txt,.md,.doc,.docx,.pdf"
          />
        </div>
      ),
    },
    {
      key: 'preprocess',
      label: '多文件预处理',
      children: (
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Form form={textForm} layout="vertical">
            <Form.Item
              label="项目"
              name="project_id"
              rules={[{ required: true, message: '请选择项目' }]}
            >
              <Select placeholder="请选择项目">
                {projects.map((p) => (
                  <Option key={p.id} value={p.id}>
                    {p.name}
                  </Option>
                ))}
              </Select>
            </Form.Item>
          </Form>

          <Upload.Dragger
            multiple
            accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
            beforeUpload={(file) => {
              setPreprocessFiles(prev => [...prev, file]);
              return false;
            }}
            onRemove={(file) => {
              setPreprocessFiles(prev => prev.filter(f => f.name !== file.name));
            }}
            fileList={preprocessFiles.map((f, i) => ({
              uid: `${i}`,
              name: f.name,
              status: 'done' as const,
            }))}
          >
            <p><InboxOutlined style={{ fontSize: 48 }} /></p>
            <p>拖拽或点击选择文件（支持多选）</p>
            <p style={{ fontSize: 12 }}>
              支持: PDF, DOCX, MD, TXT, PNG, JPG
            </p>
          </Upload.Dragger>

          <Input
            placeholder="需求文档标题（可选，默认取第一个文件名）"
            value={preprocessTitle}
            onChange={e => setPreprocessTitle(e.target.value)}
          />

          <Button
            type="primary"
            block
            size="large"
            loading={preprocessing}
            disabled={preprocessFiles.length === 0}
            onClick={async () => {
              const projectId = textForm.getFieldValue('project_id');
              if (!projectId) {
                message.error('请先选择项目');
                return;
              }
              setPreprocessing(true);
              try {
                const result = await preprocessRequirements(projectId, preprocessFiles, preprocessTitle);
                message.success('需求文档已生成');
                navigate(`/requirements/${result.id}`);
              } catch (e: any) {
                message.error(e.response?.data?.detail || '预处理失败');
              } finally {
                setPreprocessing(false);
              }
            }}
          >
            预处理需求文档
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={3} style={{ marginBottom: 24 }}>
        新建分析
      </Title>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}