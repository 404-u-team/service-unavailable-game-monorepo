<script lang="ts">
  import { Tooltip } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import { CircleHelp } from '@lucide/svelte';

  let { label, text, trigger, content, class: className, href, newTab = false, onclick, delay = 350, side = 'top',
    hoverTarget, showTrigger = true }: {
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
    hoverTarget?: Element;
    showTrigger?: boolean;
  } = $props();

  let open = $state(false);
  let anchor = $state<HTMLElement>();
  let pointerAnchor = $state<{ getBoundingClientRect: () => DOMRect }>();

  $effect(() => {
    const target = hoverTarget;
    const duration = delay;
    if (!target) return;
    const listeners = new AbortController();
    const options = { signal: listeners.signal };
    let timer: ReturnType<typeof setTimeout> | undefined;
    let x: number, y: number;

    function enter(event: PointerEvent) {
      if (event.pointerType === 'touch' || event.buttons) return;
      move(event);
      timer = setTimeout(() => {
        const bounds = new DOMRect(x, y, 0, 0);
        pointerAnchor = { getBoundingClientRect: () => bounds };
        open = true;
      }, duration);
    }

    function move(event: PointerEvent) {
      x = event.clientX;
      y = event.clientY;
    }

    function leave() {
      clearTimeout(timer);
      if (pointerAnchor) {
        open = false;
        pointerAnchor = undefined;
      }
    }

    target.addEventListener('pointerenter', (event) => enter(event as PointerEvent), options);
    target.addEventListener('pointermove', (event) => move(event as PointerEvent), options);
    target.addEventListener('pointerleave', leave, options);
    target.addEventListener('pointerdown', leave, options);
    target.addEventListener('pointercancel', leave, options);
    return () => { listeners.abort(); leave(); };
  });

  function showFloatingTooltip(element: HTMLElement) {
    element.showPopover();
  }
</script>

{#snippet triggerContent()}{#if trigger}{@render trigger()}{:else}<CircleHelp size={18} aria-hidden="true" />{/if}{/snippet}

<Tooltip.Provider delayDuration={delay} disableCloseOnTriggerClick disableHoverableContent={Boolean(pointerAnchor)}>
  <Tooltip.Root bind:open onOpenChange={(value) => { if (!value) pointerAnchor = undefined; }}>
    {#if showTrigger}
      <span class="anchor" bind:this={anchor}>
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
      </span>
    {/if}
    <Tooltip.Portal to={anchor?.closest<HTMLElement>('.sui-overlay') ?? undefined}>
      <Tooltip.Content role="tooltip" class="sui-tooltip" {side} sideOffset={pointerAnchor ? 14 : 6} collisionPadding={12} strategy="fixed" hideWhenDetached customAnchor={pointerAnchor}>
        {#snippet child({ props, wrapperProps })}
          <div {...wrapperProps} class="floating-tooltip" popover="manual" use:showFloatingTooltip>
            <div {...props}>{#if content}{@render content()}{:else}{text}{/if}</div>
          </div>
        {/snippet}
      </Tooltip.Content>
    </Tooltip.Portal>
  </Tooltip.Root>
</Tooltip.Provider>

<style>
  .anchor { display: inline-flex; flex: none; }
  .floating-tooltip { inset: auto; margin: 0; padding: 0; border: 0; background: transparent; overflow: visible; }
</style>

