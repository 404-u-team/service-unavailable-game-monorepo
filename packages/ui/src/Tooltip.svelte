<script lang="ts">
  import { Tooltip } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import { CircleHelp } from '@lucide/svelte';

  let { label, text, trigger, content, class: className, href, newTab = false, onclick, delay = 350, side = 'top' }: {
    label: string;
    text?: string;
    trigger?: Snippet;
    content?: Snippet;
    class?: string;
    href?: string;
    newTab?: boolean;
    onclick?: () => void;
    delay?: number;
    side?: 'top' | 'right' | 'bottom' | 'left';
  } = $props();

  let open = $state(false);
  let anchor = $state<HTMLElement>();

  function showFloatingTooltip(element: HTMLElement) {
    element.showPopover();
  }
</script>

{#snippet triggerContent()}{#if trigger}{@render trigger()}{:else}<CircleHelp size={18} aria-hidden="true" />{/if}{/snippet}

<span class="anchor" bind:this={anchor}>
<Tooltip.Provider delayDuration={delay} disableCloseOnTriggerClick>
  <Tooltip.Root bind:open>
    <Tooltip.Trigger type="button" class={trigger ? className : ['sui-button', className]} data-variant={trigger ? undefined : 'ghost'} data-icon-only={trigger ? undefined : ''} aria-label={label}
      onclick={() => { if (onclick) onclick(); else if (!href) open = trigger ? true : !open; }}>
      {#snippet child({ props })}
        {#if href}
          <a {...props} {href} target={newTab ? '_blank' : undefined} rel={newTab ? 'noopener' : undefined}>
            {@render triggerContent()}
          </a>
        {:else}
          <button {...props}>{@render triggerContent()}</button>
        {/if}
      {/snippet}
    </Tooltip.Trigger>
    <Tooltip.Portal to={anchor?.closest<HTMLElement>('.sui-overlay') ?? undefined}>
      <Tooltip.Content role="tooltip" class="sui-tooltip" {side} sideOffset={6} collisionPadding={12} strategy="fixed" hideWhenDetached>
        {#snippet child({ props, wrapperProps })}
          <div {...wrapperProps} class="floating-tooltip" popover="manual" use:showFloatingTooltip>
            <div {...props}>{#if content}{@render content()}{:else}{text}{/if}</div>
          </div>
        {/snippet}
      </Tooltip.Content>
    </Tooltip.Portal>
  </Tooltip.Root>
</Tooltip.Provider>
</span>

<style>
  .anchor { display: inline-flex; flex: none; }
  .floating-tooltip { inset: auto; margin: 0; padding: 0; border: 0; background: transparent; overflow: visible; }
</style>

