<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLButtonAttributes } from 'svelte/elements';

  type Options = { variant?: 'secondary' | 'primary' | 'ghost' | 'danger'; block?: boolean };
  type Content = { iconOnly: true; 'aria-label': string } | { iconOnly?: false; 'aria-label'?: string };
  type Props = Omit<HTMLButtonAttributes, 'children' | 'aria-label'> & Options & Content & { children: Snippet };

  let { variant = 'secondary', block = false, iconOnly, children, class: className, type = 'button', ...attrs }: Props = $props();
</script>

<button {...attrs} {type} class={['sui-button', className]} data-variant={variant}
  data-block={block || undefined} data-icon-only={iconOnly || undefined}>
  {@render children()}
</button>
