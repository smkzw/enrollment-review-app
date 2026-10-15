/**
 * 图标集：统一使用 lucide-react（1.31.0，ISC 许可 —— 与 MIT 同为宽松许可，见执行报告依赖记录）。
 * 图标一律为装饰性（aria-hidden），中文可访问名称与工具提示由承载控件提供
 * （spec: component-guidelines §Accessibility；合同 §7.1“图标按钮必须有可见中文工具提示和可访问名称”）。
 */

import {
  ArrowLeft,
  ArrowLeftRight,
  ArrowRight,
  ArrowUpDown,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  CircleDot,
  CircleHelp,
  CirclePause,
  CircleSlash,
  ClipboardList,
  Eye,
  File,
  FileBarChart,
  FileClock,
  FileText,
  LayoutGrid,
  ListChecks,
  Menu,
  Quote,
  RefreshCw,
  RotateCw,
  Scale,
  ScrollText,
  Server,
  TriangleAlert,
  UserRound,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";

interface IconProps {
  size?: number;
}

function Icon({
  icon: Component,
  size = 16,
}: { icon: LucideIcon } & IconProps) {
  return <Component size={size} aria-hidden="true" />;
}

/** 菜单（打开侧栏） */
export function MenuIcon(props: IconProps) {
  return <Icon icon={Menu} {...props} />;
}

/** 关闭（抽屉/弹层） */
export function CloseIcon(props: IconProps) {
  return <Icon icon={X} {...props} />;
}

/** 今日工作：勾选清单 */
export function TodayIcon(props: IconProps) {
  return <Icon icon={ListChecks} {...props} />;
}

/** 项目看板：矩阵 */
export function BoardIcon(props: IconProps) {
  return <Icon icon={LayoutGrid} {...props} />;
}

/** 打开/直达（进入审核节点） */
export function OpenIcon(props: IconProps) {
  return <Icon icon={ArrowRight} {...props} />;
}

/** 明确障碍：警示三角 */
export function BarrierIcon(props: IconProps) {
  return <Icon icon={TriangleAlert} {...props} />;
}

/** 缺口：感叹号圆 */
export function GapIcon(props: IconProps) {
  return <Icon icon={CircleAlert} {...props} />;
}

/** 冲突：双向箭头 */
export function ConflictIcon(props: IconProps) {
  return <Icon icon={ArrowLeftRight} {...props} />;
}

/** 需专业判断：研究者（人） */
export function JudgmentIcon(props: IconProps) {
  return <Icon icon={UserRound} {...props} />;
}

/** 后续关注/提醒：眼睛 */
export function AttentionIcon(props: IconProps) {
  return <Icon icon={Eye} {...props} />;
}

/** 未发现明确障碍：对勾圆 */
export function ClearIcon(props: IconProps) {
  return <Icon icon={CircleCheck} {...props} />;
}

/** 已完成 */
export function CheckIcon(props: IconProps) {
  return <Icon icon={Check} {...props} />;
}

/** 正在处理：旋转箭头 */
export function RunningIcon(props: IconProps) {
  return <Icon icon={RefreshCw} {...props} />;
}

/** 可恢复：暂停圆 */
export function ResumeIcon(props: IconProps) {
  return <Icon icon={CirclePause} {...props} />;
}

/** 已取消：斜杠圆 */
export function CancelledIcon(props: IconProps) {
  return <Icon icon={CircleSlash} {...props} />;
}

/** 需重新核对：循环 */
export function StaleIcon(props: IconProps) {
  return <Icon icon={RotateCw} {...props} />;
}

/** 帮助：问号圆 */
export function HelpIcon(props: IconProps) {
  return <Icon icon={CircleHelp} {...props} />;
}

/** 排序箭头 */
export function SortIcon(props: IconProps) {
  return <Icon icon={ArrowUpDown} {...props} />;
}

/** 方案工作台：方案文档 */
export function ProtocolIcon(props: IconProps) {
  return <Icon icon={BookOpen} {...props} />;
}

/** 受试者与资料：受试者集合 */
export function SubjectsIcon(props: IconProps) {
  return <Icon icon={Users} {...props} />;
}

/** 入排工作台：天平（入选/排除判断） */
export function WorkbenchIcon(props: IconProps) {
  return <Icon icon={Scale} {...props} />;
}

/** 行动中心：待办清单 */
export function ActionsIcon(props: IconProps) {
  return <Icon icon={ClipboardList} {...props} />;
}

/** 报告：报表文档 */
export function ReportsIcon(props: IconProps) {
  return <Icon icon={FileBarChart} {...props} />;
}

/** 任务与系统：服务器/系统 */
export function TasksIcon(props: IconProps) {
  return <Icon icon={Server} {...props} />;
}

/** 方案文档（新增/当前版本） */
export function ProtocolFileIcon(props: IconProps) {
  return <Icon icon={FileText} {...props} />;
}

/** 报告文档 */
export function ReportFileIcon(props: IconProps) {
  return <Icon icon={File} {...props} />;
}

/** 时间线/历史记录 */
export function HistoryIcon(props: IconProps) {
  return <Icon icon={FileClock} {...props} />;
}

/** 返回上一项 */
export function BackIcon(props: IconProps) {
  return <Icon icon={ArrowLeft} {...props} />;
}

/** 摘录/引文（页内摘录定位） */
export function ExcerptIcon(props: IconProps) {
  return <Icon icon={Quote} {...props} />;
}

/** 文本（文本范围定位） */
export function TextRangeIcon(props: IconProps) {
  return <Icon icon={ScrollText} {...props} />;
}

/** 文件（仅页码定位/原始文件） */
export function PageOnlyIcon(props: IconProps) {
  return <Icon icon={File} {...props} />;
}

/** 坐标区域定位（bbox） */
export function BboxIcon(props: IconProps) {
  return <Icon icon={CircleDot} {...props} />;
}

/** 展开（向右） */
export function ChevronRightIcon(props: IconProps) {
  return <Icon icon={ChevronRight} {...props} />;
}

/** 收起（向下） */
export function ChevronDownIcon(props: IconProps) {
  return <Icon icon={ChevronDown} {...props} />;
}
