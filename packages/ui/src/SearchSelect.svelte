<script lang="ts" module>
  export type Option = { value: string; label: string; disabled?: boolean; reason?: string };
</script>

<script lang="ts">
  import Popover from './Popover.svelte';
  import { Check, ChevronDown, Search, X } from '@lucide/svelte';
  import Button from './Button.svelte';
  import TextInput from './TextInput.svelte';
  import type { DashboardTranslate } from './dashboard';
  import type { HTMLButtonAttributes } from 'svelte/elements';

  let { options, selected, choose, label, t, multiple = false, searchable = false, ...attributes }: HTMLButtonAttributes & {
    t: DashboardTranslate; options: readonly Option[]; selected: string[]; choose: (values: string[]) => void; label: string;
    multiple?: boolean; searchable?: boolean;
  } = $props();
  const uid = $props.id();
  let anchor: HTMLButtonElement | undefined = $state();
  let menu: HTMLDivElement | undefined = $state();
  let search: HTMLInputElement | undefined = $state();
  let open = $state(false);
  let query = $state('');
  const visible = $derived(options.filter((option) => option.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())));
  const chosen = $derived(options.filter((option) => selected.includes(option.value)));

  function optionsInMenu() {
    return Array.from(menu?.querySelectorAll<HTMLButtonElement>('button[role=option]:not(:disabled)') ?? []);
  }

  function reveal() {
    menu?.showPopover();
    open = true;
    queueMicrotask(() => (search ?? optionsInMenu().find((option) => option.getAttribute('aria-selected') === 'true') ?? optionsInMenu()[0] ?? menu)?.focus());
  }

  function toggle() {
    if (open) menu?.hidePopover();
    else reveal();
  }

  function pick(value: string) {
    choose(multiple
      ? selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value]
      : [value]);
    if (!multiple) {
      menu?.hidePopover();
      anchor?.focus();
    }
  }

  function keys(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      menu?.hidePopover();
      anchor?.focus();
      return;
    }
    if (!['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
    if (event.target === search && (event.key === 'Home' || event.key === 'End')) return;
    event.preventDefault();
    const entries = optionsInMenu();
    const current = entries.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === 'ArrowUp' && current === 0 && search) { search.focus(); return; }
    const index = event.key === 'Home' ? 0 : event.key === 'End' || (event.key === 'ArrowUp' && current < 0) ? entries.length - 1
      : Math.max(0, Math.min(entries.length - 1, current + (event.key === 'ArrowDown' ? 1 : -1)));
    entries[index]?.focus();
  }
</script>

<button {...attributes} bind:this={anchor} type="button" class="choice sui-control" role="combobox" aria-label={label}
  aria-expanded={open} aria-controls={uid} onclick={toggle}
  onkeydown={(event) => { if (!open && ['ArrowDown', 'ArrowUp'].includes(event.key)) { event.preventDefault(); reveal(); } }}>
  <span>{chosen.length ? (multiple ? t('{0} selected', [chosen.length]) : chosen[0].label) : t('Select…')}</span><ChevronDown size={15} />
</button>
{#if multiple && chosen.length}
  <div class="chips">
    {#each chosen as item (item.value)}
      <button type="button" class="chip" aria-label={t('Remove {0}', [item.label])} onclick={() => pick(item.value)}>{item.label}<X size={12} /></button>
    {/each}
  </div>
{/if}
<Popover {anchor} bind:element={menu}
  ontoggle={(event) => { open = event.newState === 'open'; if (!open) query = ''; }} onkeydown={keys}>
  {#if searchable}
    <div class="search"><Search size={14} /><TextInput bind:element={search} type="search" aria-label={t('Search options')} placeholder={t('Search options')} bind:value={query} /></div>
  {/if}
  <div class="options" id={uid} role="listbox" aria-label={open ? label : undefined} aria-multiselectable={multiple || undefined}>
    {#each visible as option (option.value)}
      <button class="option" type="button" role="option" aria-selected={selected.includes(option.value)}
        disabled={option.disabled} data-value={option.value} onclick={() => pick(option.value)}>
        <span>{option.label}{#if option.reason}<small>{option.reason}</small>{/if}</span>
        {#if selected.includes(option.value)}<Check size={15} />{/if}
      </button>
    {:else}<p class="muted">{t('No matching options')}</p>
    {/each}
  </div>
  {#if multiple && selected.length}<Button class="clear" onclick={() => choose([])}>{t('Clear selection')}</Button>{/if}
</Popover>

<style>
  .choice, .chip { display: flex; align-items: center; justify-content: space-between; gap: 7px; color: var(--sui-text); background: var(--sui-raised); border: 1px solid var(--sui-control-border); border-radius: 7px; text-align: start; }
  .choice { min-height: var(--sui-target); width: 100%; padding: 5px 10px; font-size: 13px; }
  .choice span { min-width: 0; overflow-wrap: anywhere; }
  .choice :global(svg), .chip :global(svg) { flex: none; }
  .chips { display: flex; flex-wrap: wrap; gap: var(--sui-space-1); margin-top: 5px; }
  .chip { font-size: 11px; padding: 4px 7px; }
  .option { padding: 8px; min-height: var(--sui-target); display: flex; align-items: center; justify-content: space-between; width: 100%; gap: 6px; border: 0; border-radius: 5px; text-align: start; background: transparent; color: var(--sui-text); font-size: 13px; }
  .option:disabled { opacity: .65; }
  .option:is(:focus-visible, :hover):not(:disabled), .option[aria-selected='true'] { background: var(--sui-tint); }
  .option small { display: block; color: var(--sui-muted); }
  .search { display: flex; align-items: center; gap: 6px; padding: 4px; }
  .search :global(input) { width: 100%; min-width: 0; }
  :global(.clear.sui-button) { margin: 4px; }
  .options p { padding: 8px; margin: 0; color: var(--sui-muted); }
</style>
