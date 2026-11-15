# Service Unavailable UI

A private Svelte 5 design system and Storybook for the Service Unavailable workbench. The package has its own Bun lockfile. It can run without the game API or database.

## Run and verify

Install Bun 1.4.2 and Node.js 22.12 or newer. From the repository root:

```sh
cd packages/ui
bun install --frozen-lockfile
bun run storybook
```

Open [Storybook](http://localhost:6006). The **Design system** section contains the guide, color palette, typography, and spacing. **Patterns / Workbench** shows a composed capacity dashboard. The globe in the toolbar switches the component examples between English and Russian.

```sh
bun run check
bun run build-storybook
bun x playwright install chromium firefox
bun run test
TEST_BROWSER=firefox bun run test
```

The static catalog is built in `storybook-static/`.

## Use in a Svelte project

The package exposes its Svelte source and CSS. To adopt it later, add a local dependency on `@service-unavailable/ui` pointing to this directory. Import the theme once in the application entry point and import components by name. Tokens live on `:root` so they also reach overlays mounted on the document body.

```svelte
<script lang="ts">
  import '@service-unavailable/ui/theme.css';
  import { Button, Form, FormField, Slider } from '@service-unavailable/ui';

  let allocation = $state(50);
</script>

<Form ondata={(data) => console.log(data.get('traffic'))}>
  <FormField label={t('Traffic allocation')}>
    {#snippet children(control)}
      <Slider {...control} name="traffic" bind:value={allocation} min={0} max={100} step={5}
        manualLabel={t('Exact traffic allocation')} unit="%"
        manualStepLabels={{ decrease: t('Decrease {0}', [t('Traffic allocation')]), increase: t('Increase {0}', [t('Traffic allocation')]) }} />
    {/snippet}
  </FormField>
  <Button type="submit" variant="primary">{t('Save settings')}</Button>
</Form>
```

Bring the host application’s `t()` function into the script. Inputs preserve native attributes such as `name`, `required`, `min`, `max`, and `step` where applicable. Numeric controls use native validation and keyboard input with custom step buttons. Provide localized `stepLabels` for `NumberInput`. The `unit` appears beside the number within the field border and is included in the accessible description. Give `Select` a `name` to submit its value and apply required validation. Supply a finite value aligned to the step for a slider. When manual entry is enabled, only the numeric field has a form name, and invalid entries stay in the field for correction.

`Slideover` accepts a localized `resizeLabel` to enable resizing. Bind `width` to keep the preferred pixel width in the host. The panel fills narrow screens. Toasts count down for six seconds by default. Set `duration` in milliseconds or use `0` to keep an item available until dismissed. The countdown pauses while the toast is hovered or contains keyboard focus and when the document is hidden.

## Frontend audit

| Workbench reference | Reusable package components |
| --- | --- |
| `controls/`, `ProductSettings.svelte`, and configuration forms | `Button`, `TextInput`, `NumberInput`, `Textarea`, `Slider`, `Select`, `Checkbox`, `Switch`, `Form`, `FormField` |
| Workbench navigation, `Guide.svelte`, and expandable finance and demand rows | `NavTabs`, `Tabs`, `Accordion`, `Disclosure`, `Dropdown` |
| `Modal.svelte`, architecture detail panels, and `Help.svelte` | `Modal`, `Slideover`, `Tooltip` |
| Server banners and architecture event feedback | `Alert`, `Toaster` and `createToasts()` |
| `workbench/Chart.svelte`, `Meter.svelte`, dashboard and finance cards | `Chart` (line and bar), `Meter`, `Badge`, `Panel`, `PageColumns` |

The current package covers presentation and interaction. Topology editing, onboarding, simulation data, domain-specific diagnoses, and server actions belong to the game. The game still uses its existing components.

The [Nuxt UI component catalog](https://ui.nuxt.com/llms.txt) and [repository](https://github.com/nuxt/ui) informed the component inventory. The workbench’s existing theme informed the visuals.

## Embeddable dashboard

Pass a stable definition for each widget. A definition includes an ID, a title, a Svelte snippet for content, and optional defaults for the grid placement and settings. `Dashboard` renders the toolbar and widget frames and handles placement, movement, sizing, and visibility.

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { Dashboard, parseDashboardState, type DashboardState } from '@service-unavailable/ui';
  import { t } from './i18n';

  let restored = $state.raw<DashboardState | null>(null);

  onMount(() => {
    restored = parseDashboardState(localStorage.getItem('infrastructure-dashboard'));
  });

  function saveLayout(snapshot: DashboardState) {
    localStorage.setItem('infrastructure-dashboard', JSON.stringify(snapshot));
  }
</script>

{#snippet traffic()}
  <!-- Use the product's data or a component here. -->
{/snippet}

<Dashboard title={t('Infrastructure dashboard')} {t}
  widgets={[{ id: 'traffic', title: t('Incoming traffic'), content: traffic }]}
  snapshot={restored} onchange={saveLayout} />
```

Load a saved object or serialized JSON into `snapshot` to restore the whole board. An invalid replacement leaves the board as it was. The callback fires once per completed drag or resize and after each committed settings, visibility, or reset change. Imports, canceled gestures, and viewport changes leave the callback quiet. Store the returned object in the host application. With `bind:this`, call `getSnapshot()` for an independent copy of the current dashboard, including its initial layout.

Snapshots are versioned JSON. Placement uses zero-based grid coordinates with positive column and row spans. Each widget has a `visible` flag and JSON `settings`. Keep IDs stable across releases. Missing definitions are skipped, new widgets take their defaults, and conflicting rectangles are moved down. The editor can accept a widget-specific `settings(widget, patch)` snippet. Patches are applied when the widget form is saved.

At narrow container widths the dashboard becomes a one-column list. It follows grid order until the user makes a separate change to the list order, which is saved in `mobileOrder`. Numeric controls in the widget settings offer another way to move or resize a widget. Pass `readonly` for a display-only board. See **Patterns / Dashboard / Editable dashboard** for an example that stores each change and imports or exports a complete JSON snapshot.
