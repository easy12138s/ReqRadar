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
        setError(data.error_message || '分析失败');
      }
    } catch {
      setError('加载分析信息失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTask();
  }, [id]);

  const handleComplete = () => {
    fetchTask();
    message.success('分析已完成');
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
      message.success('正在重试');
      fetchTask();
    } catch {
      message.error('重试失败');
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
        title="错误"
        subTitle={error}
        extra={
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/analyses')}>
            返回分析列表
          </Button>
        }
      />
    );
  }

  if (!task) {
    return <Empty description="分析任务未找到" />;
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
          分析 #{task.id.slice(0, 8)}
        </Title>
        <Space>
          {isFailed && (
            <Button icon={<ReloadOutlined />} onClick={handleRetry}>
              重试
            </Button>
          )}
          {isComplete && (
            <Button
              type="primary"
              icon={<FileTextOutlined />}
              onClick={() => navigate(`/reports/${task.id}`)}
            >
              查看报告
            </Button>
          )}
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/analyses')}>
            返回
          </Button>
        </Space>
      </div>

      <Card style={{ marginBottom: 24 }}>
        <Descriptions column={2}>
          <Descriptions.Item label="状态">
            <Tag color={isComplete ? 'success' : isFailed ? 'error' : 'processing'}>
              {task.status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="类型">
            <Tag>{task.input_type}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="风险">
            <RiskBadge level={task.risk_level} score={task.risk_score} showScore />
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
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
          title="分析完成"
          subTitle="报告已生成，可以查看"
          extra={
            <Button
              type="primary"
              icon={<FileTextOutlined />}
              onClick={() => navigate(`/reports/${task.id}`)}
            >
              查看报告
            </Button>
          }
        />
      )}

      {isFailed && (
        <Result
          status="error"
          title="分析失败"
          subTitle={task.error_message || '分析过程中发生错误'}
          extra={
            <Button icon={<ReloadOutlined />} onClick={handleRetry}>
              重试分析
            </Button>
          }
        />
      )}
    </div>
  );
}