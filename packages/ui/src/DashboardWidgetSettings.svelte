<script lang="ts">
  import { untrack } from 'svelte';
  import Button from './Button.svelte';
  import Form from './Form.svelte';
  import FormField from './FormField.svelte';
  import NumberInput from './NumberInput.svelte';
  import type { DashboardTranslate, DashboardWidgetDefinition, DashboardWidgetState } from './dashboard';
  import { dashboardLastRow, dashboardLimits } from './dashboard';

  let { definition, widget, columns, mobilePosition, mobileCount, t, oncancel, onsave }: {
    definition: DashboardWidgetDefinition;
    widget: DashboardWidgetState;
    columns: number;
    mobilePosition?: number;
    mobileCount: number;
    t: DashboardTranslate;
    oncancel: () => void;
    onsave: (widget: DashboardWidgetState, position?: number) => void;
  } = $props();

  let column = $state<number | undefined>(untrack(() => widget.placement.x + 1));
  let row = $state<number | undefined>(untrack(() => widget.placement.y + 1));
  let gridWidth = $state<number | undefined>(untrack(() => widget.placement.width));
  let gridHeight = $state<number | undefined>(untrack(() => widget.placement.height));
  let position = $state<number | undefined>(untrack(() => mobilePosition));
  let settings = $state.raw(untrack(() => widget.settings));
  const limits = $derived(dashboardLimits(definition, columns));
  const draft = $derived({ ...widget, settings });

  function stepLabels(label: string) {
    return { decrease: t('Decrease {0}', [label]), increase: t('Increase {0}', [label]) };
  }
</script>

<Form ondata={() => {
  if (column === undefined || row === undefined || gridWidth === undefined || gridHeight === undefined) return;
  onsave({ ...draft, placement: { x: column - 1, y: row - 1, width: gridWidth, height: gridHeight } }, position);
}}>
  {#if mobilePosition !== undefined}
    <FormField label={t('Position in the list')}>
      {#snippet children(control)}
        <NumberInput {...control} bind:value={position} min={1} max={mobileCount} required
          stepLabels={stepLabels(t('Position in the list'))} />
      {/snippet}
    </FormField>
  {/if}
  <fieldset>
    <legend>{t('Grid placement')}</legend>
    <div class="fields">
      <FormField label={t('Start column')}>
        {#snippet children(control)}
          <NumberInput {...control} bind:value={column} min={1} max={columns - (gridWidth ?? limits.minWidth) + 1} required
            stepLabels={stepLabels(t('Start column'))} />
        {/snippet}
      </FormField>
      <FormField label={t('Start row')}>
        {#snippet children(control)}
          <NumberInput {...control} bind:value={row} min={1} max={Math.max(dashboardLastRow + 1, widget.placement.y + 1)} required
            stepLabels={stepLabels(t('Start row'))} />
        {/snippet}
      </FormField>
      <FormField label={t('Width in columns')}>
        {#snippet children(control)}
          <NumberInput {...control} bind:value={gridWidth} min={limits.minWidth} max={limits.maxWidth} required
            stepLabels={stepLabels(t('Width in columns'))} />
        {/snippet}
      </FormField>
      <FormField label={t('Height in rows')}>
        {#snippet children(control)}
          <NumberInput {...control} bind:value={gridHeight} min={limits.minHeight} max={limits.maxHeight} required
            stepLabels={stepLabels(t('Height in rows'))} />
        {/snippet}
      </FormField>
    </div>
  </fieldset>
  {@render definition.settings?.(draft, (patch) => settings = { ...settings, ...patch })}
  <div class="actions">
    <Button onclick={oncancel}>{t('Cancel')}</Button>
    <Button type="submit" variant="primary">{t('Save settings')}</Button>
  </div>
</Form>

<style>
  fieldset { min-inline-size: 0; margin: 0; padding: var(--sui-space-3); border: 1px solid var(--sui-border); border-radius: var(--sui-radius); }
  legend { padding-inline: var(--sui-space-1); font-weight: 600; }
  .fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 9.5rem), 1fr)); gap: var(--sui-space-3); }
  .actions { display: flex; flex-wrap: wrap; justify-content: end; gap: var(--sui-space-2); }
</style>
