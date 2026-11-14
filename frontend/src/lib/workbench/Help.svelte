<script lang="ts">
  import { CircleHelp } from '@lucide/svelte';
  let { label, text, open }: { label: string; text: string; open?: () => void } = $props();
  let expanded = $state(false);
  let dismissed = $state(false);
  const tooltipId = $props.id();
</script>

<span role="presentation" class="help" class:expanded class:dismissed
  onpointerleave={() => { expanded = false; dismissed = false; }}>
  <button class="btn icon-btn" type="button" aria-label={label} aria-describedby={tooltipId}
    onfocus={() => dismissed = false}
    onblur={() => { expanded = false; dismissed = false; }}
    onkeydown={(event) => { if (event.key === 'Escape') { expanded = false; dismissed = true; event.stopPropagation(); } }}
    onclick={() => { if (open) open(); else { expanded = !expanded; dismissed = false; } }}>
    <CircleHelp size={15} />
  </button>
  <span role="tooltip" id={tooltipId}>{text}</span>
</span>

<style>
  .help { position: relative; flex: none; }
  .help button { width: 34px; min-width: 34px; min-height: 34px; }
  [role="tooltip"] { position: absolute; z-index: 5; display: none; inset: calc(100% + 4px) 0 auto auto;
    width: min(220px, 65vw); padding: 8px 10px; color: var(--text); background: var(--surface);
    border: 1px solid var(--border); border-radius: 6px; font: 12px/1.5 var(--sans); box-shadow: 0 6px 18px #0008;
  }
  .help:focus-within [role="tooltip"], .help.expanded [role="tooltip"] { display: block; }
  .help.dismissed [role="tooltip"] { display: none; }
  @media (hover: hover) { .help:not(.dismissed):hover [role="tooltip"] { display: block; } }
</style>
