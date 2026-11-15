<script lang="ts">
  import { Modal, Slideover } from '@service-unavailable/ui';
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

  onDestroy(() => {
    if (opener) requestAnimationFrame(() => {
      if (!openDialog() && opener.isConnected && document.activeElement === document.body) opener.focus({ preventScroll: true });
    });
  });
</script>

<Overlay bind:open={() => true, (open) => { if (!open) close(); }}
  {title} description={subtitle} closeLabel={t('Close dialog')} returnFocus={opener}
  contentAttributes={{ 'data-tutorial-scroll': '' }} closeAttributes={{ 'data-tutorial': target.close }}
  {...(side ? { side, width, onWidthChange: resize, resizeLabel: resize ? t('Resize component inspector') : undefined } : { wide })}
  {children} {footer} />
