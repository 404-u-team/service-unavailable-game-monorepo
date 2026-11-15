<script lang="ts">
  import { Tooltip } from 'bits-ui';
  import { CircleHelp } from '@lucide/svelte';

  let { label, text, delay = 350, side = 'top' }: {
    label: string;
    text: string;
    delay?: number;
    side?: 'top' | 'right' | 'bottom' | 'left';
  } = $props();

  let open = $state(false);
</script>

<Tooltip.Provider delayDuration={delay} ignoreNonKeyboardFocus disableCloseOnTriggerClick>
  <Tooltip.Root bind:open>
    <Tooltip.Trigger type="button" class="sui-button" data-variant="ghost" data-icon-only aria-label={label}
      onclick={() => open = !open}>
      <CircleHelp size={18} aria-hidden="true" />
    </Tooltip.Trigger>
    <Tooltip.Portal>
      <Tooltip.Content role="tooltip" class="sui-tooltip" {side} sideOffset={6} collisionPadding={12}>{text}</Tooltip.Content>
    </Tooltip.Portal>
  </Tooltip.Root>
</Tooltip.Provider>

