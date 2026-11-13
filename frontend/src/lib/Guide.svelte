<script lang="ts">
  import { componentIcon, tutorial } from './labels';
  import type { Catalog, Game, Kind } from './types';
  let { catalog, game, link }: { catalog: Catalog; game?: Game; link?: (section: 'build' | 'monitor') => string } = $props();
  const kinds = $derived(Object.keys(catalog.components) as Kind[]);
</script>

<div class="stack">
  {#if game && link}
    <section class="panel pad stack">
      <div><p class="eyebrow">Onboarding</p><h2>First deployment</h2></div>
      <ol class="steps">
        {#each tutorial as step, index}
          <li class:current={index === game.tutorial}>
            <span class="index">{index < game.tutorial ? '✓' : index + 1}</span>
            <div><strong>{step.title}</strong><p class="muted">{step.text}</p>
              {#if index === game.tutorial}<a href={link(step.section)} class="btn">Open {step.section === 'build' ? 'topology' : 'telemetry'}</a>{/if}
            </div>
          </li>
        {/each}
      </ol>
    </section>
  {/if}
  <section class="panel pad stack">
    <h2>Component reference</h2>
    {#each kinds as kind}
      {@const definition = catalog.components[kind]}
      {@const Icon = componentIcon[kind]}
      <details>
        <summary><Icon size={17} /> {definition.name}</summary>
        <p>{definition.description}</p>
        {#if catalog.connections[kind].length}<small>Outgoing connections · {catalog.connections[kind].map((target) => catalog.components[target].name).join(', ')}</small>{/if}
      </details>
    {/each}
    <details>
      <summary>Scaling and shared dependencies</summary>
      <p>Scale vertically to add resources to one instance or horizontally to add instances. Shared databases still receive the requests handled by all API instances. Check reads and writes independently when evaluating a database bottleneck.</p>
    </details>
    <details>
      <summary>Game time and drafts</summary>
      <p>One simulation step advances ten minutes of game time. Changes made in a draft take effect after deployment. Pausing stops audience changes, bills, revenue and active development.</p>
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
