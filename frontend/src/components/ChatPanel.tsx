import { useEffect, useState, useRef } from 'react';
import { Input, Button, message } from 'antd';
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
  const msgListRef = useRef<HTMLDivElement>(null);

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
    <div style={{ padding: '12px 16px' }}>
      <div
        ref={msgListRef}
        className="no-scrollbar"
        style={{ maxHeight: 240, overflow: 'auto', marginBottom: 12 }}
      >
        {messages.length === 0 ? (
          <div style={{ color: '#64748b', fontSize: 13, padding: 8 }}>
            暂无对话，输入问题开始追问
          </div>
        ) : (
          messages.map((msg, i) => (
            <div
              key={i}
              style={{
                marginBottom: 8,
                padding: '8px 12px',
                borderRadius: 8,
                background: msg.role === 'user' ? 'rgba(0,184,212,0.1)' : 'rgba(124,58,237,0.08)',
                fontSize: 13,
                lineHeight: 1.6,
                color: '#e2e8f0',
              }}
            >
              <div style={{ fontSize: 11, color: '#8b949e', marginBottom: 4, fontWeight: 600 }}>
                {msg.role === 'user' ? '👤 用户' : '🤖 助手'}
              </div>
              <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {msg.content}
              </div>
            </div>
          ))
        )}
        <div ref={listEndRef} />
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={2}
          placeholder="输入追问..."
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          style={{ flex: 1 }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading}
          style={{ flexShrink: 0 }}
        >
          发送
        </Button>
        <Button
          icon={<SaveOutlined />}
          onClick={handleSave}
          disabled={versionNumber === undefined}
          style={{ flexShrink: 0 }}
        >
          保存
        </Button>
      </div>
    </div>
  );
}
