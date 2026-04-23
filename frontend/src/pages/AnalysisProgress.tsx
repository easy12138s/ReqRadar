import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  Typography,
  Spin,
  Empty,
  Result,
  message,
  Descriptions,
  Tag,
  Space,
} from 'antd';
import {
  FileTextOutlined,
  ReloadOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import type { AnalysisTask } from '@/types/api';
import { getAnalysis, retryAnalysis } from '@/api/analyses';
import { StepProgress } from '@/components/StepProgress';
import { RiskBadge } from '@/components/RiskBadge';

const { Title } = Typography;

export function AnalysisProgress() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<AnalysisTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTask = async () => {
    if (!id) return;
    try {
      const data = await getAnalysis(id);
      setTask(data);
      if (data.status === 'failed') {
        setError(data.error_message || 'Analysis failed');
      }
    } catch {
      setError('Failed to load analysis');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTask();
  }, [id]);

  const handleComplete = () => {
    fetchTask();
    message.success('Analysis completed');
  };

  const handleError = (msg: string) => {
    setError(msg);
    fetchTask();
  };

  const handleRetry = async () => {
    if (!id) return;
    try {
      await retryAnalysis(id);
      setError(null);
      message.success('Analysis retrying');
      fetchTask();
    } catch {
      message.error('Failed to retry');
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!task && error) {
    return (
      <Result
        status="error"
        title="Error"
        subTitle={error}
        extra={
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/analyses')}>
            Back to Analyses
          </Button>
        }
      />
    );
  }

  if (!task) {
    return <Empty description="Analysis not found" />;
  }

  const isComplete = task.status === 'completed';
  const isFailed = task.status === 'failed';

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
          Analysis #{task.id.slice(0, 8)}
        </Title>
        <Space>
          {isFailed && (
            <Button icon={<ReloadOutlined />} onClick={handleRetry}>
              Retry
            </Button>
          )}
          {isComplete && (
            <Button
              type="primary"
              icon={<FileTextOutlined />}
              onClick={() => navigate(`/reports/${task.id}`)}
            >
              View Report
            </Button>
          )}
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/analyses')}>
            Back
          </Button>
        </Space>
      </div>

      <Card style={{ marginBottom: 24 }}>
        <Descriptions column={2}>
          <Descriptions.Item label="Status">
            <Tag color={isComplete ? 'success' : isFailed ? 'error' : 'processing'}>
              {task.status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Type">
            <Tag>{task.input_type}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Risk">
            <RiskBadge level={task.risk_level} score={task.risk_score} showScore />
          </Descriptions.Item>
          <Descriptions.Item label="Created">
            {new Date(task.created_at).toLocaleString()}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {!isComplete && !isFailed && id && (
        <StepProgress
          taskId={id}
          status={task.status}
          onComplete={handleComplete}
          onError={handleError}
        />
      )}

      {isComplete && (
        <Result
          status="success"
          title="Analysis Complete"
          subTitle="Your report is ready for review"
          extra={
            <Button
              type="primary"
              icon={<FileTextOutlined />}
              onClick={() => navigate(`/reports/${task.id}`)}
            >
              View Report
            </Button>
          }
        />
      )}

      {isFailed && (
        <Result
          status="error"
          title="Analysis Failed"
          subTitle={task.error_message || 'An error occurred during analysis'}
          extra={
            <Button icon={<ReloadOutlined />} onClick={handleRetry}>
              Retry Analysis
            </Button>
          }
        />
      )}
    </div>
  );
}
