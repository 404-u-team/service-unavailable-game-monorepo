<script lang="ts">
  import { useStore, useSvelteFlow } from '@xyflow/svelte';
  import { findPlacement, type CanvasTools } from './placement';
  import type { Point } from '../types';
  import type { Rect } from './routing';

  let { container, size, obstacles, guides, bindPlacement, transientMove, nodePosition }: {
    guides: Partial<Point>;
    nodePosition: (id: string) => Point | undefined;
    transientMove: (moving: boolean) => void;
    container: HTMLElement; size: Pick<Rect, 'width' | 'height'>; obstacles: Rect[];
    bindPlacement: (tools?: CanvasTools) => void;
  } = $props();
  const store = useStore();
  const { fitView, screenToFlowPosition, getViewport, setCenter } = useSvelteFlow();

  function view(): Rect {
    const bounds = container.getBoundingClientRect();
    const start = screenToFlowPosition({ x: bounds.left + 10, y: bounds.top + 10 });
    const end = screenToFlowPosition({ x: bounds.right - 10, y: bounds.bottom - 10 });
    return { ...start, width: end.x - start.x, height: end.y - start.y };
  }

  function reveal(point: Point, permanent = true) {
    const area = view();
    if (point.x >= area.x && point.y >= area.y &&
        point.x + size.width <= area.x + area.width && point.y + size.height <= area.y + area.height) return;
    const { zoom } = getViewport();
    const visibleZoom = Math.max(.15, Math.min(zoom, (container.clientWidth - 20) / size.width, (container.clientHeight - 20) / size.height));
    if (!permanent) transientMove(true);
    void setCenter(point.x + size.width / 2, point.y + size.height / 2, { zoom: visibleZoom })
      .finally(() => { if (!permanent) transientMove(false); });
  }

  $effect(() => {
    bindPlacement({
      fit: () => { void fitView(); },
      place: () => findPlacement(view(), size, obstacles),
      reveal,
      revealNode: (id) => {
        const point = nodePosition(id);
        if (point) reveal(point, false);
      }
    });
    return () => bindPlacement();
  });
</script>

{#if guides.x !== undefined}
  <div class="guide vertical" style:left={`${store.viewport.x + guides.x * store.viewport.zoom}px`}></div>
{/if}
{#if guides.y !== undefined}
  <div class="guide horizontal" style:top={`${store.viewport.y + guides.y * store.viewport.zoom}px`}></div>
{/if}

<style>
  .guide { position: absolute; z-index: 1001; pointer-events: none; border-color: var(--primary); border-style: dashed; opacity: .8; }
  .vertical { inset-block: 0; border-width: 0 0 0 1px; }
  .horizontal { inset-inline: 0; border-width: 1px 0 0; }
</style>
