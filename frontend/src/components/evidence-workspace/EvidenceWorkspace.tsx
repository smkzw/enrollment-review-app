/**
 * 宽屏三栏证据工作台骨架（design.md §8.2 / 任务）。
 * - 左侧文件与页清单、中部识别文本/风险核对、右侧连续原文件页图。
 * - 用 CSS Grid + fr 保持流体，不固化屏幕像素；分栏可拖动/键盘调整比例。
 * - 右栏连续呈现不可变原始页图；只有通过真实性核验的区域坐标才绘制重点框。
 */

import { useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";

export interface EvidenceWorkspaceProps {
  leftTitle: string;
  leftContent: ReactNode;
  centerTitle: string;
  centerContent: ReactNode;
  rightTitle: string;
  rightContent: ReactNode;
}

const HANDLE_WIDTH = 8;
const MIN_LEFT = 20;
const MAX_LEFT = 55;
const MIN_CENTER = 30;
const MAX_CENTER = 65;
const MIN_RIGHT = 18;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function EvidenceWorkspace({
  leftTitle,
  leftContent,
  centerTitle,
  centerContent,
  rightTitle,
  rightContent,
}: EvidenceWorkspaceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [cols, setCols] = useState<{ left: number; center: number }>({
    left: 24,
    center: 44,
  });

  function beginResize(handle: 0 | 1) {
    return (event: ReactPointerEvent<HTMLDivElement>) => {
      event.preventDefault();
      const startX = event.clientX;
      const startCols = cols;
      const onMove = (move: PointerEvent) => {
        const rect = containerRef.current?.getBoundingClientRect();
        if (rect === undefined || rect.width === 0) return;
        const delta = ((move.clientX - startX) / rect.width) * 100;
        if (handle === 0) {
          const left = clamp(startCols.left + delta, MIN_LEFT, MAX_LEFT);
          const center = clamp(
            startCols.center - delta * 0.5,
            MIN_CENTER,
            MAX_CENTER,
          );
          setCols({ left, center });
        } else {
          const center = clamp(startCols.center + delta, MIN_CENTER, MAX_CENTER);
          const left = clamp(startCols.left - delta * 0.3, MIN_LEFT, MAX_LEFT);
          setCols({ left, center });
        }
      };
      const onUp = () => {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    };
  }

  function onResizeKey(handle: 0 | 1) {
    return (event: React.KeyboardEvent<HTMLDivElement>) => {
      const step =
        event.key === "ArrowRight" || event.key === "ArrowDown" ? 2 : event.key === "ArrowLeft" || event.key === "ArrowUp" ? -2 : 0;
      if (step === 0) return;
      event.preventDefault();
      setCols((current) => {
        if (handle === 0) {
          const left = clamp(current.left + step, MIN_LEFT, MAX_LEFT);
          const center = clamp(current.center - step * 0.5, MIN_CENTER, MAX_CENTER);
          return { left, center };
        }
        const center = clamp(current.center + step, MIN_CENTER, MAX_CENTER);
        const left = clamp(current.left - step * 0.3, MIN_LEFT, MAX_LEFT);
        return { left, center };
      });
    };
  }

  const right = clamp(100 - cols.left - cols.center, MIN_RIGHT, 100 - MIN_LEFT - MIN_CENTER);

  return (
    <div
      ref={containerRef}
      className="evidence-workspace"
      style={{
        gridTemplateColumns: `minmax(0, ${cols.left}fr) ${HANDLE_WIDTH}px minmax(0, ${cols.center}fr) ${HANDLE_WIDTH}px minmax(0, ${right}fr)`,
      }}
    >
      <section className="evidence-workspace__col evidence-workspace__col--left" aria-label={leftTitle}>
        <h3 className="evidence-workspace__title">{leftTitle}</h3>
        {leftContent}
      </section>
      <div
        className="evidence-workspace__resizer"
        role="separator"
        aria-orientation="vertical"
        aria-label="调整左栏宽度"
        tabIndex={0}
        onPointerDown={beginResize(0)}
        onKeyDown={onResizeKey(0)}
      />
      <section className="evidence-workspace__col evidence-workspace__col--center" aria-label={centerTitle}>
        <h3 className="evidence-workspace__title">{centerTitle}</h3>
        {centerContent}
      </section>
      <div
        className="evidence-workspace__resizer"
        role="separator"
        aria-orientation="vertical"
        aria-label="调整中栏宽度"
        tabIndex={0}
        onPointerDown={beginResize(1)}
        onKeyDown={onResizeKey(1)}
      />
      <section className="evidence-workspace__col evidence-workspace__col--right" aria-label={rightTitle}>
        <h3 className="evidence-workspace__title">{rightTitle}</h3>
        {rightContent}
      </section>
    </div>
  );
}
