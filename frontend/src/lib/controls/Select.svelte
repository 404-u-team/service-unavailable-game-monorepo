<script lang="ts">
  import { SearchSelect, Select, type SearchSelectOption } from '@service-unavailable/ui';
  import type { ComponentProps } from 'svelte';
  import { t } from '../i18n.svelte';

  let { options, value = $bindable(''), label, onchange, searchable = false, ...attributes }:
    Omit<ComponentProps<typeof Select>, 'options' | 'value' | 'onValueChange' | 'onchange'> & {
      options: SearchSelectOption[]; value?: string; label: string; onchange?: (value: string) => void; searchable?: boolean;
    } = $props();

  function choose(next: string) {
    value = next;
    onchange?.(next);
  }
</script>

{#if searchable}
  <SearchSelect id={attributes.id} disabled={attributes.disabled} data-tutorial={attributes['data-tutorial']} {options} {label} {t} searchable selected={[value]} choose={([next]) => choose(next)} />
{:else}
  <Select {...attributes} {options} {value} aria-label={label} placeholder={t('Select…')} onValueChange={choose} />
{/if}
