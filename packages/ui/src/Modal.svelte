<script lang="ts">
  import Overlay from './Overlay.svelte';
  import type { OverlayProps } from './types';

  let { open = $bindable(false), ...props }: OverlayProps & { wide?: boolean } = $props();
</script>

<Overlay {...props} bind:open />
