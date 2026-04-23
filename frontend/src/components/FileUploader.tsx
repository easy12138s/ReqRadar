import { useState, useCallback } from 'react';
import { Upload, Button, message } from 'antd';
import { UploadOutlined, InboxOutlined } from '@ant-design/icons';
import type { UploadFile, UploadProps } from 'antd/es/upload';

interface FileUploaderProps {
  onUpload: (file: File) => Promise<void>;
  accept?: string;
  maxSize?: number;
  disabled?: boolean;
}

export function FileUploader({
  onUpload,
  accept = '.txt,.md,.doc,.docx,.pdf',
  maxSize = 10 * 1024 * 1024,
  disabled = false,
}: FileUploaderProps) {
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);

  const handleChange: UploadProps['onChange'] = useCallback(({ fileList: newFileList }) => {
    setFileList(newFileList.slice(-1));
  }, []);

  const beforeUpload = useCallback(
    (file: File) => {
      if (file.size > maxSize) {
        message.error(`File must be smaller than ${maxSize / 1024 / 1024}MB`);
        return Upload.LIST_IGNORE;
      }
      return false;
    },
    [maxSize]
  );

  const handleUpload = useCallback(async () => {
    const file = fileList[0]?.originFileObj;
    if (!file) {
      message.error('Please select a file');
      return;
    }

    setUploading(true);
    try {
      await onUpload(file);
      setFileList([]);
      message.success('Upload successful');
    } catch {
      message.error('Upload failed');
    } finally {
      setUploading(false);
    }
  }, [fileList, onUpload]);

  return (
    <div>
      <Upload.Dragger
        fileList={fileList}
        onChange={handleChange}
        beforeUpload={beforeUpload}
        accept={accept}
        disabled={disabled || uploading}
        multiple={false}
        style={{ padding: 24 }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">Click or drag file to this area to upload</p>
        <p className="ant-upload-hint">
          Supports {accept} files up to {maxSize / 1024 / 1024}MB
        </p>
      </Upload.Dragger>
      <Button
        type="primary"
        onClick={handleUpload}
        loading={uploading}
        disabled={fileList.length === 0 || disabled}
        icon={<UploadOutlined />}
        style={{ marginTop: 16 }}
        block
      >
        {uploading ? 'Uploading' : 'Start Upload'}
      </Button>
    </div>
  );
}
