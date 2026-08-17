/**
 * 手工修订草稿补丁：仅改写展示性文本字段（子项标题、方案原文摘录），
 * 不重排规则、不推导临床语义、不改变编号/逻辑/来源绑定结构。
 * 输入为候选草稿内容（ProtocolDeconstructionDraft 快照），输出打补丁后的深拷贝。
 */

interface ComponentTextPatch {
  title: string;
  sourceExcerpts: string[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function clone(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(clone);
  if (isRecord(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, clone(item)]),
    );
  }
  return value;
}

/**
 * 按 rule_component_id 打补丁：改写 proposed_rules[].components[] 的 title，
 * 以及 component_drafts[].source_excerpts。找不到匹配子项时原样返回（不做静默改写）。
 */
export function patchComponentText(
  content: Record<string, unknown>,
  componentId: string,
  patch: ComponentTextPatch,
): Record<string, unknown> {
  const next = clone(content) as Record<string, unknown>;
  const rules = Array.isArray(next.proposed_rules)
    ? (next.proposed_rules as unknown[])
    : [];
  let matched = false;
  for (const rawRule of rules) {
    if (!isRecord(rawRule)) continue;
    const components = Array.isArray(rawRule.components)
      ? (rawRule.components as unknown[])
      : [];
    rawRule.components = components.map((rawComponent) => {
      if (!isRecord(rawComponent)) return rawComponent;
      if (rawComponent.rule_component_id !== componentId) return rawComponent;
      matched = true;
      return {
        ...rawComponent,
        title: patch.title,
      };
    });
  }
  const drafts = Array.isArray(next.component_drafts)
    ? (next.component_drafts as unknown[])
    : [];
  next.component_drafts = drafts.map((rawDraft) => {
    if (!isRecord(rawDraft)) return rawDraft;
    const proposed = rawDraft.proposed_component;
    if (isRecord(proposed) && proposed.rule_component_id !== componentId) {
      return rawDraft;
    }
    return {
      ...rawDraft,
      source_excerpts: patch.sourceExcerpts,
    };
  });
  return matched ? next : content;
}
