<script lang="ts">
  import CheckControl from './CheckControl.svelte';
  import type { CheckProps } from './types';

  let { checked = $bindable(false), ...attrs }: CheckProps = $props();
</script>

<CheckControl {...attrs} bind:checked switchStyle />
