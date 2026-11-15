<script lang="ts">
  import { Check, ChevronDown } from '@lucide/svelte';
  import { Select } from 'bits-ui';
  import type { HTMLSelectAttributes } from 'svelte/elements';
  import type { SelectOption } from './types';

  let { options, value = $bindable(''), placeholder, name, required, autocomplete, disabled, onValueChange, class: className, ...attrs }:
    Omit<Select.TriggerProps, 'type' | 'children' | 'child' | 'ref' | 'disabled' | 'name' | 'form'> & {
      options: readonly SelectOption[];
      value?: string;
      placeholder?: string;
      name?: string;
      required?: boolean;
      disabled?: boolean;
      autocomplete?: HTMLSelectAttributes['autocomplete'];
      onValueChange?: (value: string) => void;
    } = $props();

  const selected = $derived(options.find((option) => option.value === value));
</script>

<Select.Root type="single" items={[...options]} bind:value {name} {required} {disabled} {autocomplete} {onValueChange}>
  <Select.Trigger {...attrs} class={['sui-control', 'sui-select-trigger', className]} aria-required={required || undefined}>
    <span data-placeholder={!selected || undefined}>{selected?.label ?? placeholder}</span>
    <ChevronDown size={16} aria-hidden="true" />
  </Select.Trigger>
  <Select.Portal>
    <Select.Content class="sui-menu sui-select-menu" align="start" sideOffset={6} collisionPadding={12}>
      <Select.Viewport class="sui-select-viewport">
        {#each options as option (option.value)}
          <Select.Item class="sui-menu-item sui-select-item" {...option}>
            {#snippet children({ selected: checked })}
              <span>{option.label}</span>
              {#if checked}<Check size={16} aria-hidden="true" />{/if}
            {/snippet}
          </Select.Item>
        {/each}
      </Select.Viewport>
    </Select.Content>
  </Select.Portal>
</Select.Root>

<style>
  :global(.sui-control.sui-select-trigger) { display: flex; align-items: center; justify-content: space-between; gap: var(--sui-space-2); text-align: start; }
  :global(.sui-control.sui-select-trigger:enabled) { cursor: pointer; }
  :global(.sui-control.sui-select-trigger > svg) { flex: none; color: var(--sui-muted); }
  :global(.sui-control.sui-select-trigger[data-state='open'] > svg) { transform: rotate(180deg); }
  span { overflow-wrap: anywhere; }
  span[data-placeholder] { color: var(--sui-muted); }
  :global(.sui-menu.sui-select-menu) { --sui-menu-anchor: var(--bits-select-anchor-width); display: flex; flex-direction: column; overflow: hidden; inline-size: min(var(--sui-menu-anchor), calc(100vw - 24px)); }
  :global(.sui-select-viewport) { min-block-size: 0; max-block-size: calc(var(--bits-select-content-available-height) - 10px); }
  :global(.sui-menu-item.sui-select-item) { justify-content: space-between; gap: var(--sui-space-2); }
  :global(.sui-select-item > svg) { flex: none; color: var(--sui-primary); }
</style>
