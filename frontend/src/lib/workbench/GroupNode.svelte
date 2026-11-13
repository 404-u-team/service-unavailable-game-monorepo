<script lang="ts" module>
  import type { Node } from '@xyflow/svelte';
  export type GroupFlowNode = Node<{
    name: string; count: number; warnings: number; status: string; throughput?: number; collapsed: boolean;
    toggle: () => void;
  }, 'groupCard'>;
</script>

<script lang="ts">
  import { count, t } from '../i18n.svelte';
  import { Handle, Position, type NodeProps } from '@xyflow/svelte';
  import { Layers, ChevronDown, ChevronRight } from '@lucide/svelte';
  let { data, selected }: NodeProps<GroupFlowNode> = $props();
</script>

<div class="group" class:selected class:collapsed={data.collapsed}>
  {#if data.collapsed}<Handle type="target" position={Position.Left} isConnectable={false} />{/if}
  <div class="group-header drag-group">
    <Layers size={15} />
    <strong title={data.name}>{data.name}</strong>
    <button class="nodrag nopan" type="button" aria-label={data.collapsed ? t("Expand group") : t("Collapse group")} onclick={data.toggle}>
      {#if data.collapsed}<ChevronRight size={16} />{:else}<ChevronDown size={16} />{/if}
    </button>
  </div>
  {#if data.collapsed}
    <p class="mono">{count(data.count, 'component', 'components', ['компонент', 'компонента', 'компонентов'])} · <span class:warning={data.warnings > 0}>{t(data.status)}</span></p>
    <p class="mono">{count(data.warnings, 'warning', 'warnings', ['предупреждение', 'предупреждения', 'предупреждений'])}{#if data.throughput !== undefined} · {t('{0}/s', [Math.round(data.throughput)])}{/if}</p>
    <Handle type="source" position={Position.Right} isConnectable={false} />
  {/if}
</div>

<style>
  .group { height: 100%; border: 1px solid #475f61; border-radius: 10px; background: #5a8d9014; }
  .collapsed { background: var(--raised); }
  .selected { border-color: var(--primary); }
  .group-header { display: flex; align-items: center; gap: 7px; padding: 4px 8px; color: var(--text); cursor: grab; }
  .group-header .nodrag { flex-shrink: 0; }
  .group-header :global(svg) { flex-shrink: 0; }
  strong { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
  button { display: grid; place-items: center; border: 0; border-radius: 5px; background: var(--tint); color: var(--text); margin-left: auto; min-width: 27px; min-height: 27px; }
  p { padding: 0 9px; margin: 2px 0; color: var(--muted); font-size: 10px; }
</style>
