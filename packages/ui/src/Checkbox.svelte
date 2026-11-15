<script lang="ts">
  import CheckControl from './CheckControl.svelte';
  import type { CheckProps } from './types';

  let { checked = $bindable(false), indeterminate = $bindable(false), ...attrs }: CheckProps & { indeterminate?: boolean } = $props();
</script>

<CheckControl {...attrs} bind:checked bind:indeterminate />
