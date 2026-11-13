<script lang="ts">
  import { onMount } from 'svelte';
  import { getViewportForBounds, useSvelteFlow } from '@xyflow/svelte';
  let { container, compact, nodeIds }: { container: HTMLElement; compact: boolean; nodeIds: string[] } = $props();
  const { fitView, getNodesBounds, setViewport } = useSvelteFlow();

  onMount(() => {
    let timer: ReturnType<typeof setTimeout>;
    const resize = new ResizeObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const bounds = getNodesBounds(nodeIds);
        const { clientWidth, clientHeight } = container;
        if (!bounds.width || !bounds.height || !clientWidth || !clientHeight) {
          void fitView({ padding: .12, maxZoom: compact ? 1 : 1.13 });
          return;
        }
        void setViewport(getViewportForBounds(bounds, clientWidth, clientHeight, .15, compact ? 1 : 1.13, .12));
      }, 80);
    });
    resize.observe(container);
    return () => { resize.disconnect(); clearTimeout(timer); };
  });
</script>
