<script lang="ts">
  import type { Point, Speed } from '../types';
  import { segments } from './routing';
  import { advanceTraffic, onTrafficFrame, type Traffic } from './traffic-animation';

  let { points, rate, speed, color }: { points: Point[]; rate: number; speed: Speed; color: string } = $props();
  const traffic: Traffic = { packets: [], emission: 1, nextId: 0 };
  let packets = $state.raw<Traffic['packets']>([]);
  const route = $derived.by(() => {
    let distance = 0;
    return segments(points).flatMap(([from, to]) => {
      const length = Math.hypot(to.x - from.x, to.y - from.y);
      if (!length) return [];
      const start = distance;
      distance += length;
      return [{ from, to, start, end: distance, length }];
    });
  });
  const length = $derived(route.at(-1)?.end ?? 0);
  const active = $derived(speed > 0 && length > 0 && (rate > 0 || packets.length > 0));

  $effect(() => {
    if (active) return onTrafficFrame((seconds) => packets = advanceTraffic(traffic, length, rate, speed, seconds));
  });
</script>

{#if active}
  <g class="traffic-packets" aria-hidden="true" pointer-events="none" stroke={color}>
    {#each packets as packet (packet.id)}
      {@const segment = route.find((item) => packet.distance < item.end)}
      {#if segment}
        {@const progress = (packet.distance - segment.start) / segment.length}
        <circle class="traffic" r="3.6" fill="#f5fff0" stroke-width="1"
          cx={segment.from.x + (segment.to.x - segment.from.x) * progress}
          cy={segment.from.y + (segment.to.y - segment.from.y) * progress} />
      {/if}
    {/each}
  </g>
{/if}
