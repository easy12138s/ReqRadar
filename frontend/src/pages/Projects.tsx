import { useEffect, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Typography,
  Empty,
  Spin,
  Tag,
  message,
  Modal,
  Form,
  Input,
  Select,
} from 'antd';
import {
  PlusOutlined,
  CodeOutlined,
  CalendarOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { Project, ProjectCreate } from '@/types/api';
import { getProjects, createProject } from '@/api/projects';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

export function Projects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const fetchProjects = async () => {
    setLoading(true);
    try {
      const data = await getProjects();
      setProjects(data);
    } catch {
      message.error('Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreate = async (values: ProjectCreate) => {
    setSubmitting(true);
    try {
      await createProject(values);
      message.success('Project created');
      setModalVisible(false);
      form.resetFields();
      fetchProjects();
    } catch {
      message.error('Failed to create project');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          Projects
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalVisible(true)}
        >
          New Project
        </Button>
      </div>

      {projects.length === 0 ? (
        <Empty
          description="No projects yet"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setModalVisible(true)}
          >
            Create Project
          </Button>
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {projects.map((project) => (
            <Col xs={24} sm={12} lg={8} key={project.id}>
              <Card
                hoverable
                onClick={() => navigate(`/projects/${project.id}`)}
                title={project.name}
                extra={<CodeOutlined />}
              >
                <Paragraph ellipsis={{ rows: 2 }}>{project.description}</Paragraph>
                <div style={{ marginTop: 12 }}>
                  <Tag color="blue">{project.language}</Tag>
                  {project.framework && (
                    <Tag color="cyan">{project.framework}</Tag>
                  )}
                </div>
                <div style={{ marginTop: 12 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    <CalendarOutlined />{' '}
                    {new Date(project.created_at).toLocaleDateString()}
                  </Text>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="Create Project"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
        }}
        footer={null}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item
            label="Name"
            name="name"
            rules={[{ required: true, message: 'Please enter project name' }]}
          >
            <Input placeholder="Project name" />
          </Form.Item>
          <Form.Item
            label="Description"
            name="description"
            rules={[{ required: true, message: 'Please enter description' }]}
          >
            <Input.TextArea rows={3} placeholder="Project description" />
          </Form.Item>
          <Form.Item
            label="Language"
            name="language"
            rules={[{ required: true, message: 'Please select language' }]}
          >
            <Select placeholder="Select language">
              <Option value="python">Python</Option>
              <Option value="javascript">JavaScript</Option>
              <Option value="typescript">TypeScript</Option>
              <Option value="java">Java</Option>
              <Option value="go">Go</Option>
              <Option value="rust">Rust</Option>
              <Option value="csharp">C#</Option>
              <Option value="cpp">C++</Option>
              <Option value="other">Other</Option>
            </Select>
          </Form.Item>
          <Form.Item label="Framework" name="framework">
            <Input placeholder="Framework (optional)" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block>
              Create
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
