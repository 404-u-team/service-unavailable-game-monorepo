<script lang="ts">
  import { Tooltip } from 'bits-ui';
  import { CircleHelp } from '@lucide/svelte';

  let { label, text, href, newTab = false, onclick, delay = 350, side = 'top' }: {
    label: string;
    text: string;
    href?: string;
    newTab?: boolean;
    onclick?: () => void;
    delay?: number;
    side?: 'top' | 'right' | 'bottom' | 'left';
  } = $props();

  let open = $state(false);
  let anchor = $state<HTMLElement>();
</script>

<span class="anchor" bind:this={anchor}>
<Tooltip.Provider delayDuration={delay} disableCloseOnTriggerClick>
  <Tooltip.Root bind:open>
    <Tooltip.Trigger type="button" class="sui-button" data-variant="ghost" data-icon-only aria-label={label}
      onclick={() => { if (onclick) onclick(); else if (!href) open = !open; }}>
      {#snippet child({ props })}
        {#if href}
          <a {...props} {href} target={newTab ? '_blank' : undefined} rel={newTab ? 'noopener' : undefined}>
            <CircleHelp size={18} aria-hidden="true" />
          </a>
        {:else}
          <button {...props}><CircleHelp size={18} aria-hidden="true" /></button>
        {/if}
      {/snippet}
    </Tooltip.Trigger>
    <Tooltip.Portal to={anchor?.closest<HTMLElement>('.sui-overlay') ?? undefined}>
      <Tooltip.Content role="tooltip" class="sui-tooltip" {side} sideOffset={6} collisionPadding={12}>{text}</Tooltip.Content>
    </Tooltip.Portal>
  </Tooltip.Root>
</Tooltip.Provider>
</span>

<style>
  .anchor { display: inline-flex; flex: none; }
</style>

