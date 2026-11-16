<script lang="ts">
  import { Dashboard, type DashboardState, type DashboardWidgetDefinition } from '@service-unavailable/ui';
  import { onMount } from 'svelte';
  import type { Snippet } from 'svelte';
  import { t } from '../i18n.svelte';
  import { target } from './onboarding';
  import { isGameDashboardChange, readGameDashboardLayout, writeGameDashboard, type DashboardSection } from './dashboard-layouts';

  let { gameId, section, title, tools, widgets }: {
    gameId: string; section: DashboardSection; title: string;
    tools?: Snippet;
    widgets: DashboardWidgetDefinition[];
  } = $props();

  let snapshot = $state.raw<DashboardState | null>(null);
  let dashboard = $state<{ showWidget: (id: string) => void }>();

  export function showWidget(id: string) {
    dashboard?.showWidget(id);
  }

  onMount(() => {
    function reload() {
      try { snapshot = readGameDashboardLayout(gameId)[section]; } catch { /* Storage is optional. */ }
    }
    function update(event: StorageEvent) {
      if (isGameDashboardChange(gameId, section, event.key)) reload();
    }
    reload();
    window.addEventListener('storage', update);
    return () => window.removeEventListener('storage', update);
  });

  function save(layout: DashboardState) {
    try { writeGameDashboard(gameId, section, layout); } catch { /* The board retains changes in memory. */ }
  }
</script>

<Dashboard bind:this={dashboard} {title} {tools} {widgets} {snapshot} {t} headingLevel={1} rowHeight={42} onchange={save}
  editButtonAttributes={{ 'data-tutorial': target.dashboard }} />
