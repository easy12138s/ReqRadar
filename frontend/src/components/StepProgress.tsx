import { useEffect, useRef, useState, useCallback } from 'react';
import { Steps, Card, Typography } from 'antd';
import type { AnalysisStatus } from '@/types/api';
import type { WebSocketMessage } from '@/types/websocket';

const { Title, Text } = Typography;

const STEP_ITEMS = [
  { title: 'Queue', description: 'Waiting in queue' },
  { title: 'Extract', description: 'Extracting requirements' },
  { title: 'Analyze', description: 'Analyzing risks' },
  { title: 'Report', description: 'Generating report' },
  { title: 'Review', description: 'Reviewing findings' },
  { title: 'Complete', description: 'Analysis complete' },
];

interface StepProgressProps {
  taskId: string;
  status: AnalysisStatus;
  onComplete?: () => void;
  onError?: (message: string) => void;
}

export function StepProgress({ taskId, status, onComplete, onError }: StepProgressProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [message, setMessage] = useState('Connecting...');
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/analyses/${taskId}/ws?token=${token}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setMessage('Connected, waiting for updates...');
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
          setMessage(data.message || `Status: ${data.status}`);
          if (data.status === 'completed') {
            setCurrentStep(5);
            onComplete?.();
          } else if (data.status === 'failed') {
            onError?.('Analysis failed');
          }
        } else if (msg.type === 'error') {
          const data = msg.data as { message: string };
          setMessage(`Error: ${data.message}`);
          onError?.(data.message);
        } else if (msg.type === 'complete') {
          setCurrentStep(5);
          onComplete?.();
        }
      } catch {
        setMessage('Received invalid message');
      }
    };

    ws.onerror = () => {
      setMessage('WebSocket error occurred');
      onError?.('WebSocket error');
    };

    ws.onclose = () => {
      setMessage('Connection closed');
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
      <Title level={4}>Analysis Progress</Title>
      <Steps
        direction="vertical"
        current={currentStep}
        items={STEP_ITEMS.map((item, index) => ({
          title: item.title,
          description: index === currentStep ? message : item.description,
          status: getStepStatus(index) as 'wait' | 'process' | 'finish' | 'error',
        }))}
      />
      <div style={{ marginTop: 16 }}>
        <Text type="secondary">{message}</Text>
      </div>
    </Card>
  );
}
