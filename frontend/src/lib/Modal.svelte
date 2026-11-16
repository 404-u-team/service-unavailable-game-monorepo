<script lang="ts">
  import { Modal, Slideover } from '@service-unavailable/ui';
  import { goto } from '$app/navigation';
  import { onDestroy } from 'svelte';
  import { target } from './workbench/onboarding';
  import { openDialog } from './workbench/spotlight';
  import { t } from './i18n.svelte';
  import type { Snippet } from 'svelte';

  let { title, subtitle, children, footer, close, wide = false, side, width, resize }:
    { title: string; subtitle?: string; children: Snippet; footer?: Snippet; close: () => void;
      wide?: boolean; side?: 'start' | 'end'; width?: number; resize?: (width: number) => void } = $props();
  const Overlay = $derived(side ? Slideover : Modal);
  const opener = typeof document !== 'undefined' && document.activeElement instanceof HTMLElement ? document.activeElement : undefined;
  let open = $state(true);
  let afterClose: (() => void) | undefined;

  export function dismiss(after: () => void = () => close()) {
    if (!open) return;
    if (!side) { after(); return; }
    afterClose = after;
    open = false;
  }

  function followLink(event: MouseEvent) {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey
      || !(event.target instanceof Element)) return;
    const link = event.target.closest<HTMLAnchorElement>('a[href]');
    if (!link || (link.target && link.target !== '_self') || link.hasAttribute('download') || link.origin !== location.origin) return;
    event.preventDefault();
    dismiss(() => { close(); void goto(link.href); });
  }

  onDestroy(() => {
    if (opener) requestAnimationFrame(() => {
      if (!openDialog() && opener.isConnected && document.activeElement === document.body) opener.focus({ preventScroll: true });
    });
  });
</script>

<Overlay bind:open={() => open, (next) => { if (!next) dismiss(); }}
  onCloseComplete={() => afterClose?.()}
  {title} description={subtitle} closeLabel={t('Close dialog')} returnFocus={opener}
  contentAttributes={{ 'data-tutorial-scroll': '', onclick: side ? followLink : undefined }} closeAttributes={{ 'data-tutorial': target.close }}
  {...(side ? { side, width, onWidthChange: resize, resizeLabel: resize ? t('Resize component inspector') : undefined } : { wide })}
  {children} {footer} />
