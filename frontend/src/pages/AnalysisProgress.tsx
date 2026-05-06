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
  StopOutlined,
} from '@ant-design/icons';
import type { AnalysisTask, AnalysisStatus } from '@/types/api';
import { getAnalysis, retryAnalysis, cancelAnalysis } from '@/api/analyses';
import { StepProgress } from '@/components/StepProgress';
import { DimensionProgress } from '@/components/DimensionProgress';
import { RiskBadge } from '@/components/RiskBadge';
import { useWebSocket } from '../hooks/useWebSocket';

const { Title } = Typography;

export function AnalysisProgress() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<AnalysisTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dimensions, setDimensions] = useState<Record<string, string>>({});
  const [evidenceCount, setEvidenceCount] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const [stepProgressMessage, setStepProgressMessage] = useState('连接中...');
  const [maxSteps, setMaxSteps] = useState(15);

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

  const token = localStorage.getItem('access_token');
  const wsUrl = id && token
    ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/analyses/${id}/ws?token=${token}`
    : '';

  const { status: wsStatus } = useWebSocket({
    url: wsUrl,
    enabled: !!wsUrl,
    onMessage: (msg: any) => {
      if (msg.type === 'dimension_progress') {
        setDimensions(msg.dimensions || {});
        setEvidenceCount(msg.evidence_count || 0);
        setCurrentStep(msg.step || 0);
        setMaxSteps(msg.max_steps || 15);
      } else if (msg.type === 'status') {
        const data = msg.data as { status: AnalysisStatus; message?: string };
        if (data.status === 'completed') {
          setCurrentStep(5);
          setStepProgressMessage(data.message || '分析完成');
          fetchTask();
        } else if (data.status === 'failed') {
          setStepProgressMessage(data.message || '分析失败');
          fetchTask();
        } else {
          setStepProgressMessage(data.message || `状态: ${data.status}`);
        }
      } else if (msg.type === 'progress') {
        const data = msg.data as { step: number; total_steps: number; step_name: string; message: string };
        setCurrentStep(data.step);
        setStepProgressMessage(data.message || data.step_name);
      } else if (msg.type === 'complete') {
        setCurrentStep(5);
        setStepProgressMessage('分析完成');
        fetchTask();
      } else if (msg.type === 'error') {
        const data = msg.data as { message: string };
        setStepProgressMessage(`错误: ${data.message}`);
      }
    },
  });

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
        <>
          <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
            {wsStatus === 'open'
              ? <span style={{ color: '#22c55e', fontSize: 13 }}>&#9679; 已连接</span>
              : wsStatus === 'reconnecting'
              ? <span style={{ color: '#eab308', fontSize: 13 }}>&#9679; 重连中</span>
              : <span style={{ color: '#ef4444', fontSize: 13 }}>&#9679; 断开</span>
            }
          </div>
          <Card style={{ marginBottom: 24 }}>
            <DimensionProgress
              dimensions={dimensions}
              evidenceCount={evidenceCount}
              step={currentStep}
              maxSteps={maxSteps}
            />
          </Card>
            <StepProgress
              currentStep={currentStep}
              progressMessage={stepProgressMessage}
              status={task.status}
            />
          <div style={{ marginTop: 16 }}>
            <Button danger icon={<StopOutlined />} onClick={async () => {
              try { await cancelAnalysis(id); message.success('已停止分析'); }
              catch { message.error('停止失败'); }
            }}>
              停止并生成报告
            </Button>
          </div>
        </>
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