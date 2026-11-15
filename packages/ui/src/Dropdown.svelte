<script lang="ts">
  import { DropdownMenu } from 'bits-ui';
  import { ChevronDown } from '@lucide/svelte';
  import type { MenuAction } from './types';

  let { label, items, disabled = false, align = 'start' }: {
    label: string;
    items: readonly MenuAction[];
    disabled?: boolean;
    align?: 'start' | 'center' | 'end';
  } = $props();
</script>

<DropdownMenu.Root>
  <DropdownMenu.Trigger class="sui-button" disabled={disabled || !items.length}>
    {label}<ChevronDown size={16} aria-hidden="true" />
  </DropdownMenu.Trigger>
  <DropdownMenu.Portal>
    <DropdownMenu.Content class="sui-menu sui-dropdown-menu" {align} sideOffset={6} collisionPadding={12}>
      {#each items as item (item.id)}
        <DropdownMenu.Item class="sui-menu-item" disabled={item.disabled} data-tone={item.tone} onSelect={item.onSelect}>
          {item.label}
        </DropdownMenu.Item>
      {/each}
    </DropdownMenu.Content>
  </DropdownMenu.Portal>
</DropdownMenu.Root>

