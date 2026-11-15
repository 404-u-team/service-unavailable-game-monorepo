<script lang="ts">
  import { Dashboard, parseDashboardState, type DashboardState, type DashboardWidgetDefinition } from '@service-unavailable/ui';
  import { onMount } from 'svelte';
  import type { Snippet } from 'svelte';
  import { t } from '../i18n.svelte';

  let { gameId, section, title, tools, widgets }: {
    gameId: string; section: 'monitor' | 'growth' | 'finance'; title: string;
    tools?: Snippet;
    widgets: DashboardWidgetDefinition[];
  } = $props();

  const key = $derived(`service-unavailable:dashboard:${gameId}:${section}`);
  let snapshot = $state.raw<DashboardState | null>(null);
  let dashboard = $state<{ showWidget: (id: string) => void }>();

  export function showWidget(id: string) {
    dashboard?.showWidget(id);
  }

  onMount(() => {
    try { snapshot = parseDashboardState(localStorage.getItem(key)); } catch { /* Storage is optional. */ }
  });

  function save(layout: DashboardState) {
    try { localStorage.setItem(key, JSON.stringify(layout)); } catch { /* The board retains changes in memory. */ }
  }
</script>

<Dashboard bind:this={dashboard} {title} {tools} {widgets} {snapshot} {t} headingLevel={1} rowHeight={42} onchange={save} />
