import { useCallback, useEffect, useState, type Dispatch, type SetStateAction } from "react";

/**
 * 仅保存界面试用进度，支持离开页面后继续。不得用于保存临床事实或完整受试者资料。
 */
export function useSessionState<T>(
  key: string,
  initialValue: T,
  parse: (value: unknown) => T | null,
): [T, Dispatch<SetStateAction<T>>, () => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const saved = window.sessionStorage.getItem(key);
      if (saved === null) return initialValue;
      return parse(JSON.parse(saved)) ?? initialValue;
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    try {
      window.sessionStorage.setItem(key, JSON.stringify(value));
    } catch {
      // 浏览器拒绝会话存储时仍可在当前页面继续试用。
    }
  }, [key, value]);

  const reset = useCallback(() => {
    try {
      window.sessionStorage.removeItem(key);
    } catch {
      // 与上方一致：存储不可用不阻断界面操作。
    }
    setValue(initialValue);
  }, [initialValue, key]);

  return [value, setValue, reset];
}
