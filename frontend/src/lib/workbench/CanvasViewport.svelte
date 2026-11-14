<script lang="ts">
  import { useSvelteFlow } from '@xyflow/svelte';
  import { findPlacement } from './placement';
  import type { Point } from '../types';
  import type { Rect } from './routing';

  let { container, size, obstacles, bindPlacement }: {
    container: HTMLElement; size: Pick<Rect, 'width' | 'height'>; obstacles: Rect[];
    bindPlacement: (tools?: { place: () => Point; reveal: (point: Point) => void }) => void;
  } = $props();
  const { screenToFlowPosition, getViewport, setCenter } = useSvelteFlow();

  function view(): Rect {
    const bounds = container.getBoundingClientRect();
    const start = screenToFlowPosition({ x: bounds.left + 10, y: bounds.top + 10 });
    const end = screenToFlowPosition({ x: bounds.right - 10, y: bounds.bottom - 10 });
    return { ...start, width: end.x - start.x, height: end.y - start.y };
  }

  $effect(() => {
    bindPlacement({
      place: () => findPlacement(view(), size, obstacles),
      reveal: (point) => {
        const area = view();
        if (point.x >= area.x && point.y >= area.y &&
            point.x + size.width <= area.x + area.width && point.y + size.height <= area.y + area.height) return;
        const { zoom } = getViewport();
        const visibleZoom = Math.max(.15, Math.min(zoom, (container.clientWidth - 20) / size.width, (container.clientHeight - 20) / size.height));
        void setCenter(point.x + size.width / 2, point.y + size.height / 2, { zoom: visibleZoom });
      }
    });
    return () => bindPlacement();
  });
</script>
