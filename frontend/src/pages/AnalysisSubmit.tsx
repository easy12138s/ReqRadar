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
        message.error('Failed to load projects');
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
      message.success('Analysis submitted');
      navigate(`/analyses/${task.id}`);
    } catch {
      message.error('Failed to submit analysis');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    const projectId = textForm.getFieldValue('project_id');
    if (!projectId) {
      message.error('Please select a project first');
      throw new Error('No project selected');
    }
    const task = await uploadAnalysis(projectId, file);
    message.success('File uploaded and analysis started');
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
      <Empty description="Create a project first">
        <Button type="primary" onClick={() => navigate('/projects')}>
          Go to Projects
        </Button>
      </Empty>
    );
  }

  const tabItems = [
    {
      key: 'text',
      label: 'Text Input',
      children: (
        <Form
          form={textForm}
          onFinish={handleTextSubmit}
          layout="vertical"
        >
          <Form.Item
            label="Project"
            name="project_id"
            rules={[{ required: true, message: 'Please select a project' }]}
          >
            <Select placeholder="Select project">
              {projects.map((p) => (
                <Option key={p.id} value={p.id}>
                  {p.name}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            label="Requirements Text"
            name="text"
            rules={[{ required: true, message: 'Please enter requirements text' }]}
          >
            <TextArea
              rows={12}
              placeholder="Paste your requirements document here..."
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
              Submit Analysis
            </Button>
          </Form.Item>
        </Form>
      ),
    },
    {
      key: 'file',
      label: 'File Upload',
      children: (
        <div>
          <Form form={textForm} layout="vertical">
            <Form.Item
              label="Project"
              name="project_id"
              rules={[{ required: true, message: 'Please select a project' }]}
            >
              <Select placeholder="Select project">
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
        New Analysis
      </Title>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}
