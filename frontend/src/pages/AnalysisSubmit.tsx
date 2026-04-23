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
} from 'antd';
import { SendOutlined } from '@ant-design/icons';
import type { Project } from '@/types/api';
import { getProjects } from '@/api/projects';
import { createAnalysis, uploadAnalysis } from '@/api/analyses';
import { FileUploader } from '@/components/FileUploader';

const { Title } = Typography;
const { TextArea } = Input;
const { Option } = Select;

export function AnalysisSubmit() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [textForm] = Form.useForm();
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

  const handleTextSubmit = async (values: { project_id: string; text: string }) => {
    setSubmitting(true);
    try {
      const task = await createAnalysis(values);
      message.success('分析任务已提交');
      navigate(`/analyses/${task.id}`);
    } catch {
      message.error('提交分析失败');
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
    const task = await uploadAnalysis(projectId, file);
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
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={submitting}
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