<script lang="ts">
  import { Dialog } from 'bits-ui';
  import { X } from '@lucide/svelte';
  import type { Snippet } from 'svelte';
  import type { OverlayProps } from './types';

  let { open = $bindable(false), title, description, closeLabel, dismissible = true, returnFocus,
    contentAttributes, closeAttributes, side, wide = false, children, footer, width, panelId, handle }: OverlayProps & {
      side?: 'start' | 'end'; wide?: boolean; width?: number; panelId?: string; handle?: Snippet;
    } = $props();

  let opener: HTMLElement | undefined;
</script>

<Dialog.Root bind:open>
  <Dialog.Portal>
    <Dialog.Overlay class="sui-scrim" data-side={side} />
    <Dialog.Content {...contentAttributes} id={panelId} class="sui-overlay" data-side={side} data-wide={wide || undefined} inert={!open}
      style={width === undefined ? undefined : `--sui-drawer-width: ${width}px`}
      interactOutsideBehavior={dismissible ? 'close' : 'ignore'}
      escapeKeydownBehavior={dismissible ? 'close' : 'ignore'}
      onOpenAutoFocus={() => { opener = document.activeElement instanceof HTMLElement ? document.activeElement : undefined; }}
      onCloseAutoFocus={(event) => {
        const element = returnFocus?.isConnected ? returnFocus : opener;
        if (element?.isConnected) {
          event.preventDefault();
          element.focus({ preventScroll: true });
        }
      }}>
      <header>
        <div>
          <Dialog.Title class="sui-overlay-title">{title}</Dialog.Title>
          {#if description}<Dialog.Description class="sui-overlay-description">{description}</Dialog.Description>{/if}
        </div>
        <Dialog.Close {...closeAttributes} type="button" class="sui-button" data-variant="ghost" data-icon-only aria-label={closeLabel}>
          <X size={18} aria-hidden="true" />
        </Dialog.Close>
      </header>
      {@render handle?.()}
      <div class="content" data-sui-overlay-body>{@render children()}</div>
      {#if footer}<footer>{@render footer()}</footer>{/if}
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>

<style>
  :global(.sui-scrim) { position: fixed; inset: 0; z-index: var(--sui-layer-overlay); background: var(--sui-backdrop); }
  :global(.sui-overlay) {
    box-sizing: border-box; position: fixed; z-index: calc(var(--sui-layer-overlay) + 1); inset: 0; margin: auto;
    display: flex; flex-direction: column;
    inline-size: min(34rem, calc(100% - 1.5rem)); block-size: fit-content; max-block-size: calc(100dvh - 1.5rem);
    border: 1px solid var(--sui-border); border-radius: var(--sui-radius-panel);
    background: var(--sui-surface); color: var(--sui-text); box-shadow: var(--sui-shadow);
    font: var(--sui-body); overflow: clip; overflow-wrap: anywhere;
  }
  :global(.sui-overlay[data-wide]) { inline-size: min(51rem, calc(100% - 1.5rem)); }
  :global(.sui-scrim[data-side]) { transition: opacity var(--sui-motion) ease; }
  :global(.sui-scrim[data-side]:is([data-starting-style], [data-ending-style])) { opacity: 0; }
  :global(.sui-overlay[data-side]) {
    --slide-from: 100%;
    inset: 0; inset-inline-start: auto; margin: 0; inline-size: min(var(--sui-drawer-width, 28rem), 100%); block-size: 100dvh;
    max-block-size: 100dvh; border-radius: 0; transition: transform var(--sui-motion) ease;
  }
  :global(.sui-overlay[data-side]:is([data-starting-style], [data-ending-style])) { transform: translateX(var(--slide-from)); }
  :global(.sui-overlay[data-side='start']) { --slide-from: -100%; inset-inline: 0 auto; }
  :global(.sui-overlay[data-side='end']:dir(rtl)) { --slide-from: -100%; }
  :global(.sui-overlay[data-side='start']:dir(rtl)) { --slide-from: 100%; }

  header, footer { padding: var(--sui-space-3) var(--sui-space-5); }
  header { display: flex; align-items: start; justify-content: space-between; gap: var(--sui-space-2); border-block-end: 1px solid var(--sui-border); }
  :global(.sui-overlay-title) { margin: 0; font: var(--sui-title); }
  :global(.sui-overlay-description) { margin: var(--sui-space-1) 0 0; color: var(--sui-muted); }
  .content { flex: 1 1 auto; min-block-size: 0; overflow: auto; overscroll-behavior: contain; padding: var(--sui-space-5); }
  footer { border-block-start: 1px solid var(--sui-border); }
</style>
