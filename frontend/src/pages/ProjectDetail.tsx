import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card,
  Tabs,
  Typography,
  Descriptions,
  Tag,
  Table,
  Spin,
  Empty,
  Button,
  Form,
  Input,
  Select,
  message,
} from 'antd';
import {
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import type {
  Project,
  ProjectMemory,
  ProjectUpdate,
  TermEntry,
  ModuleEntry,
  TeamMember,
  HistoryEntry,
} from '@/types/api';
import { getProject, updateProject, getProjectMemory } from '@/api/projects';

const { Title, Paragraph } = Typography;
const { Option } = Select;

export function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [memory, setMemory] = useState<ProjectMemory | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  const fetchData = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [projectData, memoryData] = await Promise.all([
        getProject(id),
        getProjectMemory(id),
      ]);
      setProject(projectData);
      setMemory(memoryData);
      form.setFieldsValue(projectData);
    } catch {
      message.error('Failed to load project');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [id]);

  const handleSave = async (values: ProjectUpdate) => {
    if (!id) return;
    setSaving(true);
    try {
      const updated = await updateProject(id, values);
      setProject(updated);
      setEditing(false);
      message.success('Project updated');
    } catch {
      message.error('Failed to update project');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!project) {
    return <Empty description="Project not found" />;
  }

  const overviewContent = editing ? (
    <Form
      form={form}
      onFinish={handleSave}
      layout="vertical"
      initialValues={project}
    >
      <Form.Item
        label="Name"
        name="name"
        rules={[{ required: true }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        label="Description"
        name="description"
        rules={[{ required: true }]}
      >
        <Input.TextArea rows={4} />
      </Form.Item>
      <Form.Item
        label="Language"
        name="language"
        rules={[{ required: true }]}
      >
        <Select>
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
        <Input />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={saving} icon={<SaveOutlined />}>
          Save
        </Button>
        <Button
          icon={<CloseOutlined />}
          onClick={() => {
            setEditing(false);
            form.resetFields();
          }}
          style={{ marginLeft: 8 }}
        >
          Cancel
        </Button>
      </Form.Item>
    </Form>
  ) : (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>
          Edit
        </Button>
      </div>
      <Descriptions bordered column={1}>
        <Descriptions.Item label="Name">{project.name}</Descriptions.Item>
        <Descriptions.Item label="Description">
          <Paragraph>{project.description}</Paragraph>
        </Descriptions.Item>
        <Descriptions.Item label="Language">
          <Tag color="blue">{project.language}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Framework">
          {project.framework || '-'}
        </Descriptions.Item>
        <Descriptions.Item label="Created">
          {new Date(project.created_at).toLocaleString()}
        </Descriptions.Item>
        <Descriptions.Item label="Updated">
          {new Date(project.updated_at).toLocaleString()}
        </Descriptions.Item>
      </Descriptions>
    </div>
  );

  const tabItems = [
    {
      key: 'overview',
      label: 'Overview',
      children: overviewContent,
    },
    {
      key: 'memory',
      label: 'Memory',
      children: (
        <Tabs
          items={[
            {
              key: 'terminology',
              label: 'Terminology',
              children: (
                <Table<TermEntry>
                  dataSource={memory?.terminology || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: 'Term', dataIndex: 'term', key: 'term' },
                    { title: 'Definition', dataIndex: 'definition', key: 'definition' },
                    { title: 'Context', dataIndex: 'context', key: 'context' },
                  ]}
                  locale={{ emptyText: 'No terminology entries' }}
                />
              ),
            },
            {
              key: 'modules',
              label: 'Modules',
              children: (
                <Table<ModuleEntry>
                  dataSource={memory?.modules || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: 'Name', dataIndex: 'name', key: 'name' },
                    { title: 'Description', dataIndex: 'description', key: 'description' },
                    {
                      title: 'Responsibilities',
                      dataIndex: 'responsibilities',
                      key: 'responsibilities',
                      render: (v: string[]) => v?.map((r) => <Tag key={r}>{r}</Tag>) || '-',
                    },
                  ]}
                  locale={{ emptyText: 'No modules' }}
                />
              ),
            },
            {
              key: 'team',
              label: 'Team',
              children: (
                <Table<TeamMember>
                  dataSource={memory?.team || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: 'Name', dataIndex: 'name', key: 'name' },
                    { title: 'Role', dataIndex: 'role', key: 'role' },
                    {
                      title: 'Expertise',
                      dataIndex: 'expertise',
                      key: 'expertise',
                      render: (v: string[]) => v?.map((e) => <Tag key={e}>{e}</Tag>) || '-',
                    },
                  ]}
                  locale={{ emptyText: 'No team members' }}
                />
              ),
            },
            {
              key: 'history',
              label: 'History',
              children: (
                <Table<HistoryEntry>
                  dataSource={memory?.history || []}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: 'Event', dataIndex: 'event', key: 'event' },
                    { title: 'Details', dataIndex: 'details', key: 'details' },
                    {
                      title: 'Timestamp',
                      dataIndex: 'timestamp',
                      key: 'timestamp',
                      render: (v: string) => new Date(v).toLocaleString(),
                    },
                  ]}
                  locale={{ emptyText: 'No history entries' }}
                />
              ),
            },
          ]}
        />
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>{project.name}</Title>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}
