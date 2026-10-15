/**
 * 旧版合成数据只用于组件测试和显式视觉试用构建。
 * 正式构建不得静默回退到合成项目、受试者或审核结论。
 */
export function isInterfaceTrialMode(): boolean {
  return (
    import.meta.env.MODE === "test" ||
    import.meta.env.VITE_ENROLLMENT_INTERFACE_TRIAL === "true"
  );
}
