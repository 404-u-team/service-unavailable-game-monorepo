<script lang="ts" module>
  import type { Node, Position } from '@xyflow/svelte';
  import type { Kind } from '../types';
  export type WorkbenchNode = Node<{
    name: string; kind: Kind; meta: string; health: string; tone: string;
    change: string; use?: number; editable: boolean; vertical: boolean; input: Position; output: Position;
  }, 'workbench'>;
</script>

<script lang="ts">
  import { Handle, type NodeProps } from '@xyflow/svelte';
  import { componentIcon } from '../labels';
  import Meter from '../Meter.svelte';
  let { data, selected }: NodeProps<WorkbenchNode> = $props();
  const Icon = $derived(componentIcon[data.kind]);
</script>

<div class="node {data.tone}" class:selected class:removed={data.change === 'Pending removal'} class:vertical={data.vertical}>
  {#if data.kind !== 'source'}
    <Handle type="target" position={data.input} isConnectable={data.editable} />
  {/if}
  <div class="row">
    <span class="symbol"><Icon size={19} strokeWidth={2.1} /></span>
    <div class="identity"><strong title={data.name}>{data.name}</strong><small class="mono">{data.meta}</small></div>
  </div>
  <div class="node-status">
    {#if data.change}<span class="change">{data.change}</span>{:else}<span class="status">{data.health}</span>{/if}
    {#if data.use !== undefined}<Meter value={data.use} label={data.health} show={false} />{/if}
  </div>
  {#if data.kind !== 'monitor'}
    <Handle type="source" position={data.output} isConnectable={data.editable} />
  {/if}
</div>

<style>
  .node {
    --node-state: var(--muted);
    position: relative; display: grid; gap: 10px; width: 167px; min-height: 101px;
    padding: 11px; border: 1px solid var(--border); border-radius: 11px; background: var(--raised); text-align: left;
  }
  .node.good { --node-state: var(--primary); }
  .node.warn { --node-state: var(--warning); }
  .node.bad { --node-state: var(--error); }
  .node.selected { border-color: var(--primary); }
  .node.removed { border-style: dashed; border-color: var(--error); opacity: .65; }
  .node.vertical { width: 156px; min-height: 84px; padding: 8px 9px; gap: 6px; }
  .symbol { display: grid; place-items: center; border-radius: 7px; background: var(--tint); width: 30px; height: 30px; flex: 0 0 auto; }
  .identity { min-width: 0; }
  strong, small { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  strong { font-size: 14px; }
  small { font-size: 10px; margin-top: 2px; }
  .status, .change { font: 600 10px var(--mono); color: var(--node-state); }
  .change { color: var(--warning); }
  .node-status { display: grid; gap: 5px; }
  .node :global(.svelte-flow__handle) { width: 10px; height: 10px; border: 1px solid #42535d; background: var(--background); }
  .node :global(.svelte-flow__handle.connectable) { width: 13px; height: 13px; border-color: var(--primary); }
</style>
