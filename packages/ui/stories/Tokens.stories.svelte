<script module lang="ts">
  import { defineMeta } from '@storybook/addon-svelte-csf';
  import { PageColumns, Panel } from '@service-unavailable/ui';
  import { t } from './copy.svelte';

  const { Story } = defineMeta({ title: 'Design system/Foundations' });
  const palette = [
    { token: 'background', label: 'Canvas', hex: '#0C1013' },
    { token: 'page', label: 'Page', hex: '#111519' },
    { token: 'surface', label: 'Surface', hex: '#141C21' },
    { token: 'raised', label: 'Raised surface', hex: '#172229' },
    { token: 'control-border', label: 'Control border', hex: '#64737C' },
    { token: 'text', label: 'Text', hex: '#ECF4F2' },
    { token: 'muted', label: 'Secondary text', hex: '#92A1A8' },
    { token: 'primary', label: 'Primary and success', hex: '#C7F46C' },
    { token: 'warning', label: 'Warning', hex: '#FFB35C' },
    { token: 'danger', label: 'Danger', hex: '#FF727D' },
    { token: 'info', label: 'Information', hex: '#91D3D4' }
  ];
</script>

<Story name="Color">
  <main>
    <h1>{t('Color')}</h1>
    <PageColumns columns={4} minWidth="11rem">
      {#each palette as { token, label, hex } (token)}
        <div class="swatch">
          <div class="sample" style:background={`var(--sui-${token})`}></div>
          <strong>{t(label)}</strong>
          <small>{hex} · --sui-{token}</small>
        </div>
      {/each}
    </PageColumns>
  </main>
</Story>

<Story name="Typography and spacing">
  <main>
    <h1>{t('Typography and spacing')}</h1>
    <PageColumns columns={2} minWidth="17rem">
      <Panel>
        <div class="type">
          <div class="display">{t('Service overview')}</div><small>Space Grotesk 700 · --sui-display</small>
          <div>{t('Measurements are available for monitored servers.')}</div><small>Inter 400 · --sui-body</small>
          <code>246 {t('req/s')} · 14:00</code><small>IBM Plex Mono 500 · --sui-caption</small>
        </div>
      </Panel>
      <Panel>
        <ul>
          {#each [1, 2, 3, 4, 5, 6] as size}
            <li><span style:inline-size={`var(--sui-space-${size})`}></span><code>--sui-space-{size}</code></li>
          {/each}
        </ul>
      </Panel>
    </PageColumns>
  </main>
</Story>

<style>
  main { max-inline-size: 66rem; }
  h1 { font: var(--sui-display); margin: 0 0 var(--sui-space-5); }
  .swatch { display: grid; gap: var(--sui-space-1); border: 1px solid var(--sui-border); border-radius: var(--sui-radius); background: var(--sui-surface); padding: var(--sui-space-2); overflow-wrap: anywhere; }
  .sample { block-size: 3.5rem; border: 1px solid var(--sui-border); border-radius: var(--sui-radius-sm); }
  small { color: var(--sui-muted); }
  .type { display: grid; gap: var(--sui-space-2); }
  small + div, small + code { margin-block-start: var(--sui-space-3); }
  .display { font: var(--sui-display); }
  code { font: var(--sui-caption); }
  ul { display: grid; gap: var(--sui-space-2); list-style: none; padding: 0; margin: 0; }
  li { display: grid; grid-template-columns: 2rem 1fr; align-items: center; gap: var(--sui-space-3); }
  li span { block-size: 1rem; background: var(--sui-primary); border-radius: var(--sui-radius-sm); }
</style>
