import { useEffect, useRef, useState, useCallback } from 'react';
import { Steps, Card, Typography } from 'antd';
import type { AnalysisStatus } from '@/types/api';
import type { WebSocketMessage } from '@/types/websocket';

const { Title, Text } = Typography;

const STEP_ITEMS = [
  { title: '排队', description: '等待处理' },
  { title: '提取', description: '提取需求内容' },
  { title: '分析', description: '分析风险点' },
  { title: '报告', description: '生成分析报告' },
  { title: '审查', description: '审查分析结果' },
  { title: '完成', description: '分析完成' },
];

interface StepProgressProps {
  taskId: string;
  status: AnalysisStatus;
  onComplete?: () => void;
  onError?: (message: string) => void;
}

export function StepProgress({ taskId, status, onComplete, onError }: StepProgressProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [progressMessage, setMessage] = useState('连接中...');
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/analyses/${taskId}/ws?token=${token}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setMessage('已连接，等待更新...');
    };

    ws.onmessage = (event) => {
      try {
        const msg: WebSocketMessage = JSON.parse(event.data);
        if (msg.type === 'progress') {
          const data = msg.data as { step: number; total_steps: number; step_name: string; message: string };
          setCurrentStep(data.step);
          setMessage(data.message || data.step_name);
        } else if (msg.type === 'status') {
          const data = msg.data as { status: AnalysisStatus; message?: string };
          setMessage(data.message || `状态: ${data.status}`);
          if (data.status === 'completed') {
            setCurrentStep(5);
            onComplete?.();
          } else if (data.status === 'failed') {
            onError?.('分析失败');
          }
        } else if (msg.type === 'error') {
          const data = msg.data as { message: string };
          setMessage(`错误: ${data.message}`);
          onError?.(data.message);
        } else if (msg.type === 'complete') {
          setCurrentStep(5);
          onComplete?.();
        }
      } catch {
        setMessage('收到无效消息');
      }
    };

    ws.onerror = () => {
      setMessage('WebSocket 连接错误');
      onError?.('WebSocket 错误');
    };

    ws.onclose = () => {
      setMessage('连接已关闭');
    };
  }, [taskId, onComplete, onError]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  const getStepStatus = (index: number) => {
    if (index < currentStep) return 'finish';
    if (index === currentStep) {
      if (status === 'failed') return 'error';
      return 'process';
    }
    return 'wait';
  };

  return (
    <Card>
      <Title level={4}>分析进度</Title>
      <Steps
        direction="vertical"
        current={currentStep}
        items={STEP_ITEMS.map((item, index) => ({
          title: item.title,
          description: index === currentStep ? progressMessage : item.description,
          status: getStepStatus(index) as 'wait' | 'process' | 'finish' | 'error',
        }))}
      />
      <div style={{ marginTop: 16 }}>
        <Text type="secondary">{progressMessage}</Text>
      </div>
    </Card>
  );
}