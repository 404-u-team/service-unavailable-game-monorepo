<script lang="ts" module>
  import type { Node, Position } from '@xyflow/svelte';
  import type { Kind } from '../types';
  export type WorkbenchNode = Node<{
    name: string; kind: Kind; meta: string; health: string; tone: string;
    change: string; use?: number; editable: boolean; vertical: boolean; input: Position; output: Position; compatible?: boolean; matchPort: 'source' | 'target';
  }, 'workbench'>;
</script>

<script lang="ts">
  import { t } from '../i18n.svelte';
  import { Handle, type NodeProps } from '@xyflow/svelte';
  import { componentIcon } from '../labels';
  import Meter from '../Meter.svelte';
  let { data, selected }: NodeProps<WorkbenchNode> = $props();
  const Icon = $derived(componentIcon[data.kind]);
</script>

<div class="node {data.tone}" class:selected class:removed={data.change === t('Pending removal')} class:vertical={data.vertical} class:compatible={data.compatible === true} class:incompatible={data.compatible === false}>
  {#if data.kind !== 'source'}
    <Handle type="target" position={data.input} isConnectable={data.editable} class={data.compatible && data.matchPort === 'target' ? 'valid-port' : undefined} />
  {/if}
  <div class="row">
    <span class="symbol"><Icon size={19} strokeWidth={2.1} /></span>
    <div class="identity"><strong title={data.name}>{data.name}</strong>{#if data.meta}<small title={data.meta} class="mono">{data.meta}</small>{/if}</div>
  </div>
  <div class="node-status">
    {#if data.change}<span class="change" title={data.change}>{data.change}</span>{:else}<span class="status" title={data.health}>{data.health}</span>{/if}
    {#if data.use !== undefined}<Meter value={data.use} label={data.health} show={false} />{/if}
  </div>
  {#if data.kind !== 'monitor'}
    <Handle type="source" position={data.output} isConnectable={data.editable} class={data.compatible && data.matchPort === 'source' ? 'valid-port' : undefined} />
  {/if}
</div>

<style>
  .node {
    --node-state: var(--muted);
    position: relative; display: grid; gap: 4px; width: 100%; height: 100%; grid-template-rows: minmax(0, 1fr) auto; grid-template-columns: minmax(0, 1fr);
    padding: 11px; border: 1px solid var(--border); border-radius: 11px; background: var(--raised); text-align: left;
  }
  .node.good { --node-state: var(--primary); }
  .node.warn { --node-state: var(--warning); }
  .node.bad { --node-state: var(--error); }
  .node.selected { border-color: var(--primary); }
  .node.compatible { border-color: var(--primary); background: #23342b; box-shadow: 0 0 0 2px var(--primary), 0 0 20px #c7f46c55; }
  .node.incompatible { opacity: .35; }
  .node.removed { border-style: dashed; border-color: var(--error); opacity: .65; }
  .node.vertical { padding: 7px 9px; gap: 3px; }
  .symbol { display: grid; place-items: center; border-radius: 7px; background: var(--tint); width: 24px; height: 26px; flex: 0 0 auto; }
  .identity { flex: 1; min-width: 0; }
  .row { min-width: 0; gap: 6px; }
  strong { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-clamp: 2;
    overflow: hidden; overflow-wrap: anywhere; font-size: 13px; line-height: 1.17; }
  .node.vertical strong { font-size: 12px; }
  small { display: block; white-space: nowrap; font-size: 10px; line-height: 1.2; margin-top: 2px; }
  .status, .change { font: 600 10px var(--mono); color: var(--node-state); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .change { color: var(--warning); }
  .node-status { display: grid; grid-template-columns: minmax(0, 1fr); gap: 5px; }
  .node :global(.svelte-flow__handle) { width: 10px; height: 10px; border: 1px solid #42535d; background: var(--background); }
  .node :global(.svelte-flow__handle.connectable) { width: 13px; height: 13px; border-color: var(--primary); }
  .node :global(.svelte-flow__handle.valid-port) { width: 16px; height: 16px; border: 2px solid var(--background);
    background: var(--primary); box-shadow: 0 0 0 3px var(--primary), 0 0 15px var(--primary); }
</style>
