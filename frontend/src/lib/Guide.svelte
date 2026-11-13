<script lang="ts">
  import { Check } from '@lucide/svelte';
  import { t } from './i18n.svelte';
  import { connectionKind, connectionLabels } from './workbench/connections';
  import { componentNotes } from './workbench/details';
  import { preciseMoney } from './format';
  import { componentIcon, tutorial } from './labels';
  import type { Catalog, Game, Kind } from './types';
  let { catalog, game, link }: { catalog: Catalog; game?: Game; link?: (section: 'build' | 'monitor') => string } = $props();
  const kinds = $derived(Object.keys(catalog.components) as Kind[]);
</script>

<div class="stack">
  {#if game && link}
    <section class="panel pad stack">
      <div><p class="eyebrow">{t("Onboarding")}</p><h2>{t("First deployment")}</h2></div>
      <ol class="steps">
        {#each tutorial as step, index}
          <li class:current={index === game.tutorial}>
            <span class="index">{#if index < game.tutorial}<Check size={15} />{:else}{index + 1}{/if}</span>
            <div><strong>{t(step.title)}</strong><p class="muted">{t(step.text)}</p>
              {#if index === game.tutorial}<a href={link(step.section)} class="btn">{t("Open")} {step.section === 'build' ? t("topology") : t("telemetry")}</a>{/if}
            </div>
          </li>
        {/each}
      </ol>
    </section>
  {/if}
  <section class="panel pad stack">
    <h2>{t("Component reference")}</h2>
    {#each kinds as kind}
      {@const definition = catalog.components[kind]}
      {@const Icon = componentIcon[kind]}
      <details>
        <summary><Icon size={17} /> {t(definition.name)}</summary>
        <p>{t(definition.description)}</p>
        <p>{preciseMoney(definition.daily)} {t('base daily cost')}</p>
        <ul>{#each componentNotes[kind] as note}<li>{t(note)}</li>{/each}</ul>
        <p><strong>{t('Input connections')}</strong></p>
        <ul>{#each kinds.filter((source) => catalog.connections[source].includes(kind)) as source}
          <li>{t(catalog.components[source].name)} · {t(connectionLabels[connectionKind(catalog, source, kind)])}</li>
        {:else}<li>{t('None')}</li>{/each}</ul>
        <p><strong>{t('Output connections')}</strong></p>
        <ul>{#each catalog.connections[kind] as target}
          <li>{t(catalog.components[target].name)} · {t(connectionLabels[connectionKind(catalog, kind, target)])}</li>
        {:else}<li>{t('None')}</li>{/each}</ul>
      </details>
    {/each}
    <details>
      <summary>{t("Background processing")}</summary>
      <p>{t("After saving a message or upload, the API can submit a notification or media job to a queue. The request finishes after submission. The job completes when a worker processes it. Database writes and synchronous API work still use their normal capacity.")}</p>
      <p>{t("For example, if 30 jobs per second arrive and workers can process 20, the backlog grows by about 10 jobs per second before expiration and overflow. Increase worker capacity to drain it. A larger queue can absorb a longer burst and allows more jobs to wait.")}</p>
    </details>
    <details>
      <summary>{t("Scaling and shared dependencies")}</summary>
      <p>{t("Scale vertically to add resources to one instance or horizontally to add instances. Shared databases still receive the requests handled by all API instances. Check reads and writes independently when evaluating a database bottleneck.")}</p>
    </details>
    <details>
      <summary>{t("Game time and drafts")}</summary>
      <p>{t("One simulation step advances ten minutes of game time. Changes made in a draft take effect after deployment. Pausing stops audience changes, bills, revenue and active development.")}</p>
    </details>
  </section>
</div>

<style>
  details { background: var(--rail); border: 1px solid var(--border); border-radius: 8px; padding: 9px 13px; }
  summary { cursor: pointer; font-weight: 600; min-height: 26px; }
  summary :global(svg) { vertical-align: middle; color: var(--primary); margin: 0 5px; }
  details p { margin: 8px 0; }
  .steps { display: grid; gap: 9px; padding: 0; margin: 0; list-style: none; }
  .steps li { display: grid; grid-template-columns: 30px 1fr; gap: 10px; align-items: start; padding: 10px; }
  .steps li.current { border-radius: 8px; background: var(--rail); }
  .steps .btn { margin-top: 8px; }
  .index { display: grid; place-items: center; background: var(--tint); border-radius: 6px; height: 28px; font: 600 13px var(--mono); }
</style>
