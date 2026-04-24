import { useEffect, useState, useRef } from 'react';
import { Input, Button, List, Space, message } from 'antd';
import { SendOutlined, SaveOutlined } from '@ant-design/icons';
import { sendChatMessage, getChatHistory, saveChatVersion } from '@/api/chatback';
import type { ChatMessage } from '@/types/api';

interface ChatPanelProps {
  taskId: string;
  versionNumber?: number;
  onVersionUpdate?: (version: number) => void;
}

export function ChatPanel({ taskId, versionNumber, onVersionUpdate }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const listEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const data = await getChatHistory(taskId, versionNumber);
        setMessages(data.messages);
      } catch {
        message.error('加载聊天记录失败');
      }
    };
    fetchHistory();
  }, [taskId, versionNumber]);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    setLoading(true);
    try {
      const response = await sendChatMessage(taskId, { message: input, version_number: versionNumber });
      setInput('');
      if (response.new_version && onVersionUpdate) {
        onVersionUpdate(response.new_version);
      }
      const data = await getChatHistory(taskId, response.new_version ?? versionNumber);
      setMessages(data.messages);
    } catch {
      message.error('发送失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (versionNumber === undefined) return;
    try {
      const result = await saveChatVersion(taskId, versionNumber);
      if (result.new_version && onVersionUpdate) {
        onVersionUpdate(result.new_version);
      }
      message.success('保存成功');
    } catch {
      message.error('保存失败');
    }
  };

  return (
    <div>
      <List
        size="small"
        dataSource={messages}
        renderItem={(msg) => (
          <List.Item>
            <strong>{msg.role === 'user' ? '用户' : '助手'}:</strong> {msg.content}
          </List.Item>
        )}
        style={{ maxHeight: 300, overflow: 'auto', marginBottom: 12 }}
      />
      <div ref={listEndRef} />
      <Space style={{ width: '100%' }}>
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={2}
          placeholder="输入消息..."
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />
        <Button icon={<SendOutlined />} onClick={handleSend} loading={loading} />
        <Button icon={<SaveOutlined />} onClick={handleSave} disabled={versionNumber === undefined}>
          保存
        </Button>
      </Space>
    </div>
  );
}
