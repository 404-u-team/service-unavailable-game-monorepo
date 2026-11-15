<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLFormAttributes } from 'svelte/elements';

  let { children, onsubmit, ondata, class: className, ...attrs }: HTMLFormAttributes & {
    children: Snippet;
    ondata?: (data: FormData, event: SubmitEvent) => void;
  } = $props();
</script>

<form {...attrs} class={['form', className]} onsubmit={(event) => {
  onsubmit?.(event);
  if (ondata && !event.defaultPrevented) {
    event.preventDefault();
    ondata(new FormData(event.currentTarget, event.submitter), event);
  }
}}>
  {@render children()}
</form>

<style>
  .form { display: grid; gap: var(--sui-space-4); min-inline-size: 0; }
</style>
