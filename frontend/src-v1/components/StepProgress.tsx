import { Steps, Card, Typography } from 'antd';
import type { AnalysisStatus } from '@/types/api';

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
  currentStep: number;
  progressMessage: string;
  status: AnalysisStatus;
}

export function StepProgress({ currentStep, progressMessage, status }: StepProgressProps) {
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
