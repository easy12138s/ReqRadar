import { useEffect, useState, useRef } from 'react';
import { Input, Button, message } from 'antd';
import { SendOutlined, SaveOutlined } from '@ant-design/icons';
import { getChatHistory, saveChatVersion } from '@/api/chatback';
import type { ChatMessage } from '@/types/api';

interface ChatPanelProps {
  taskId: string;
  versionNumber?: number;
  onVersionUpdate?: (version: number) => void;
}

function parseThinkContent(text: string): { think: string; visible: string } | null {
  const match = text.match(/<think>([\s\S]*?)<\/think>/i);
  if (!match) return null;
  const think = match[1].trim();
  const visible = text.replace(match[0], '').trim();
  return { think, visible: visible || text };
}

function MessageBubble({ msg, isStreaming }: { msg: { role: string; content: string; id?: number | string }; isStreaming?: boolean }) {
  const [thinkOpen, setThinkOpen] = useState(false);
  const parsed = parseThinkContent(msg.content);

  if (parsed) {
    return (
      <div style={{
        marginBottom: 8, padding: '8px 12px', borderRadius: 8,
        background: msg.role === 'user' ? 'rgba(0,184,212,0.1)' : 'rgba(124,58,237,0.08)',
        fontSize: 13, lineHeight: 1.6, color: '#e2e8f0',
      }}>
        <div style={{ fontSize: 11, color: '#8b949e', marginBottom: 4, fontWeight: 600 }}>
          {msg.role === 'user' ? '👤 用户' : '🤖 助手'}
        </div>
        <div
          onClick={() => setThinkOpen(!thinkOpen)}
          style={{
            cursor: 'pointer', padding: '6px 10px', background: 'rgba(0,0,0,0.2)',
            borderRadius: 6, fontSize: 12, color: '#8b949e', marginBottom: 6,
            display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <span style={{ transition: 'transform 0.2s', display: 'inline-block', transform: thinkOpen ? 'rotate(90deg)' : 'none' }}>▶</span>
          💭 思考过程 ({parsed.think.length} 字)
        </div>
        {thinkOpen && (
          <div style={{
            padding: '8px 12px', background: 'rgba(0,0,0,0.25)', borderRadius: 6,
            fontSize: 12, color: '#94a3b8', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            marginBottom: 6, borderLeft: '2px solid #363b48',
          }}>
            {parsed.think}
          </div>
        )}
        {parsed.visible && (
          <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', opacity: isStreaming ? 0.9 : 1 }}>
            {parsed.visible}
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{
      marginBottom: 8, padding: '8px 12px', borderRadius: 8,
      background: msg.role === 'user' ? 'rgba(0,184,212,0.1)' : 'rgba(124,58,237,0.08)',
      fontSize: 13, lineHeight: 1.6, color: '#e2e8f0',
    }}>
      <div style={{ fontSize: 11, color: '#8b949e', marginBottom: 4, fontWeight: 600 }}>
        {msg.role === 'user' ? '👤 用户' : '🤖 助手'}
      </div>
      <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', opacity: isStreaming ? 0.9 : 1 }}>
        {msg.content}
      </div>
    </div>
  );
}

export function ChatPanel({ taskId, versionNumber, onVersionUpdate }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState('');
  const listEndRef = useRef<HTMLDivElement>(null);
  const msgListRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

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
  }, [messages, streaming]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput('');
    setLoading(true);

    const userMessage = { id: Date.now(), role: 'user' as const, content: userMsg, version_number: versionNumber || 1, created_at: '' };
    setMessages(prev => [...prev, userMessage]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const token = localStorage.getItem('access_token');
      const resp = await fetch(`/api/analyses/${taskId}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ message: userMsg, version_number: versionNumber }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const err = await resp.json();
        message.error(err.detail || '发送失败');
        return;
      }

      setStreaming('');
      const reader = resp.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let done = false;

      while (!done) {
        const { value, done: streamDone } = await reader.read();
        if (streamDone) { done = true; break; }
        const text = decoder.decode(value, { stream: true });
        const lines = text.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.token) {
                setStreaming(prev => prev + data.token);
              } else if (data.done) {
                setStreaming(prev => {
                  const newMsg = { id: data.chat_id || Date.now(), role: 'agent' as const, content: prev, version_number: versionNumber || 1, created_at: '' };
                  setMessages(prevMsgs => [...prevMsgs, newMsg]);
                  if (data.new_version && onVersionUpdate) {
                    onVersionUpdate(data.new_version);
                  }
                  return '';
                });
              } else if (data.error) {
                message.error(data.error);
              }
            } catch {}
          }
        }
      }
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        message.error('流式调用失败');
      }
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
        style={{ maxHeight: 280, overflow: 'auto', marginBottom: 12 }}
      >
        {messages.length === 0 && !streaming ? (
          <div style={{ color: '#64748b', fontSize: 13, padding: 8 }}>
            暂无对话，输入问题开始追问
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <MessageBubble key={msg.id || i} msg={msg} />
            ))}
            {streaming && (
              <MessageBubble
                msg={{ role: 'agent', content: streaming }}
                isStreaming
              />
            )}
          </>
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
          disabled={loading}
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
