<script lang="ts">
  import type { Snippet } from 'svelte';
  import { X } from '@lucide/svelte';

  let { title, subtitle, children, footer, close, wide = false }: {
    title: string; subtitle?: string; children: Snippet; footer?: Snippet; close: () => void; wide?: boolean;
  } = $props();
  let dialog: HTMLDialogElement;
  $effect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : undefined;
    dialog.showModal();
    return () => {
      dialog.close();
      queueMicrotask(() => { if (!document.querySelector('dialog[open]')) previous?.focus(); });
    };
  });
</script>

<dialog bind:this={dialog} class:wide aria-label={title} oncancel={(event) => { event.preventDefault(); close(); }}>
  <header class="row spread">
    <div><h2>{title}</h2>{#if subtitle}<p class="muted">{subtitle}</p>{/if}</div>
    <button class="btn icon-btn ghost" aria-label="Close dialog" onclick={close}><X size={17} /></button>
  </header>
  <div class="dialog-body">{@render children()}</div>
  {#if footer}<footer>{@render footer()}</footer>{/if}
</dialog>

<style>
  dialog { color: var(--text); width: min(540px, calc(100% - 28px)); max-height: min(90dvh, 850px); padding: 0; border: 1px solid var(--border); border-radius: 14px; background: var(--surface); box-shadow: 0 20px 80px #0008; overflow: auto; }
  dialog.wide { width: min(828px, calc(100% - 28px)); border-top: 5px solid var(--primary); }
  .wide header, .wide footer, .wide .dialog-body { padding-inline: 28px; }
  .wide header h2 { font-size: 28px; }
  dialog::backdrop { background: #06090bd9; }
  header, footer { padding: 17px 22px; background: var(--surface); z-index: 1; }
  header { position: sticky; top: 0; border-bottom: 1px solid var(--border); }
  header h2 { font-size: 23px; }
  header p { font-size: 13px; margin-top: 4px; }
  footer { position: sticky; bottom: 0; border-top: 1px solid var(--border); }
  .dialog-body { padding: 20px 22px; }
  @media (max-width: 600px) {
    dialog, dialog.wide { width: calc(100% - 22px); max-height: 91dvh; }
    dialog.wide { width: 100%; max-width: none; height: calc(100dvh - 66px); max-height: none; margin: 66px 0 0; border-inline: 0; border-radius: 0; }
    .wide header, .wide footer, .wide .dialog-body { padding-inline: 17px; }
    header, footer, .dialog-body { padding: 14px 15px; }
  }
</style>
