/**
 * 语义化图表配色方案
 * 按数据类型和语义分组，确保视觉一致性
 */

// 主色调序列（用于分类数据）
export const CATEGORICAL_COLORS = [
  '#00b8d4', // 青色 - 主色
  '#00c853', // 绿色 - 成功/正向
  '#ff9100', // 橙色 - 警告/注意
  '#ff5252', // 红色 - 错误/风险
  '#7c4dff', // 紫色 - 特殊/强调
  '#448aff', // 蓝色 - 信息
  '#ffd600', // 黄色 - 提示
  '#69f0ae', // 薄荷绿 - 辅助
];

// 堆叠/对比配色（用于正负对比）
export const COMPARISON_COLORS = {
  positive: '#00c853',
  negative: '#ff5252',
  neutral: '#00b8d4',
  warning: '#ff9100',
};

// 风险等级配色
export const RISK_COLORS = {
  low: '#00c853',
  medium: '#ffd600',
  high: '#ff9100',
  critical: '#ff5252',
};

// 状态配色
export const STATUS_COLORS = {
  completed: '#00c853',
  running: '#00b8d4',
  pending: '#ffd600',
  failed: '#ff5252',
  cancelled: '#9e9e9e',
};

// 项目资产分布专用配色
export const ASSET_COLORS = {
  terms: '#00b8d4',
  modules: '#00c853',
  pending: '#ff9100',
};

// 待确认变更分布配色（环形图）
export const PENDING_COLORS = [
  '#ff9100',
  '#ff5252',
  '#ffd600',
  '#ffab40',
];

// 统计卡片配色映射
export const STAT_CARD_COLORS = [
  { bg: 'rgba(0,184,212,0.1)', icon: '#00b8d4' },      // 项目 - 青色
  { bg: 'rgba(0,200,83,0.1)', icon: '#00c853' },        // 术语 - 绿色
  { bg: 'rgba(124,77,255,0.1)', icon: '#7c4dff' },      // 模块 - 紫色
  { bg: 'rgba(255,145,0,0.1)', icon: '#ff9100' },       // 待确认 - 橙色
];
