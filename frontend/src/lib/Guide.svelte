<script lang="ts">
  import { Button, Disclosure, PageColumns, Panel, Slideover, TextInput } from '@service-unavailable/ui';
  import { ArrowRight, ChevronRight, List, Search } from '@lucide/svelte';
  import { page } from '$app/state';
  import { tick } from 'svelte';
  import { locale, t } from './i18n.svelte';
  import { articles, categories, guideArticleHref, searchArticles, type Category } from './guide';
  import { connectionKind, connectionLabels } from './workbench/connections';
  import { preciseMoney } from './format';
  import { chapters, onboarding, type TutorialAction } from './workbench/onboarding';
  import TutorialControls from './workbench/TutorialControls.svelte';
  import type { Catalog, Game, Kind } from './types';

  let { catalog, game, link, busy = false, tutorialAction }: {
    catalog: Catalog; game?: Game; link?: (section: 'build' | 'monitor') => string; busy?: boolean; tutorialAction?: (action: TutorialAction) => void;
  } = $props();
  let query = $state('');
  let mobileNav = $state(false);
  const base = $derived(game ? `/game/${game.id}?view=guide` : '/?view=guide');
  const requested = $derived(page.url.searchParams.get('article') ?? (page.url.hash === '#database-guide' ? 'database-scaling' : ''));
  const active = $derived(Object.hasOwn(articles, requested) ? articles[requested] : undefined);
  const category = $derived(page.url.searchParams.get('category'));
  const kinds = $derived(Object.keys(catalog.components) as Kind[]);
  const definition = $derived(active?.kind ? catalog.components[active.kind] : undefined);
  const results = $derived(searchArticles(query, catalog, t, locale()));
  const categoriesList = Object.entries(categories) as [Category, string][];
  const byCategory = (key: Category) => Object.entries(articles).filter(([, article]) => article.category === key);
  const href = (id: string, section?: string) => guideArticleHref(base, id, section);
  const categoryHref = (key: Category) => `${base}&category=${key}#category-${key}`;

  function chooseArticle() {
    query = '';
    mobileNav = false;
  }

  $effect(() => {
    const hash = page.url.hash.slice(1);
    // A direct link can arrive before the catalog and article markup.
    if (hash && /^[a-z-]+$/.test(hash) && (active || !requested)) {
      void tick().then(() => document.getElementById(hash)?.scrollIntoView());
    }
  });
</script>

{#snippet navigation()}
  <nav class="guide-nav" aria-label={t('Guide navigation')}>
      {#each categoriesList as [key, title] (key)}
        <Disclosure variant="panel" label={t(title)} open={active?.category === key || category === key}>
          <ul>
            {#each byCategory(key) as [id, article] (id)}
              <li><a href={href(id)} onclick={chooseArticle} aria-current={requested === id ? 'page' : undefined}>{t(article.title)}</a></li>
            {/each}
          </ul>
        </Disclosure>
      {/each}
    </nav>
{/snippet}

<div class="guide">
  {#if game && tutorialAction}<TutorialControls {game} {busy} change={tutorialAction} />{/if}
  <div class="guide-header">
    <label class="row search">
      <Search size={17} /><span class="sr-only">{t('Search the Guide')}</span>
      <TextInput type="search" bind:value={query} placeholder={t('Search articles')} />
    </label>
    <Button class="categories-button" aria-haspopup="dialog" aria-expanded={mobileNav}
      onclick={() => mobileNav = true}><List size={15} /> {t('Categories')}</Button>
  </div>
  <div class="guide-layout" class:article-open={active && !query.trim()}>
    {#if active && !query.trim()}<aside class="guide-sidebar">{@render navigation()}</aside>{/if}
    <div class="guide-content">
      {#if query.trim()}
        <section class="panel pad stack" aria-label={t('Search articles')}>
          <h2>{t('Search articles')}</h2>
          <ul class="result-list">
            {#each results as { id, article } (id)}
              <li><a href={href(id)} onclick={chooseArticle}><strong>{t(article.title)}</strong><small>{t(categories[article.category])}</small></a></li>
            {:else}
              <li class="muted" role="status">{t('No matching articles.')}</li>
            {/each}
          </ul>
        </section>
      {:else if active}
        <article class="panel pad stack" id={requested === 'database-scaling' ? 'database-guide' : undefined}>
          <nav class="breadcrumbs row wrap" aria-label={t('Guide breadcrumbs')}>
            <a href={base}>{t('Guide')}</a><ChevronRight size={13} />
            <a href={categoryHref(active.category)}>{t(categories[active.category])}</a><ChevronRight size={13} />
            <span aria-current="page">{t(active.title)}</span>
          </nav>
          <h2>{t(active.title)}</h2>
          <nav class="toc" aria-label={t('On this page')}>
            <strong>{t('On this page')}</strong>
            <ul>
              {#each active.sections as section (section.id)}
                <li><a href={href(requested, section.id)}>{t(section.title)}</a></li>
              {/each}
            </ul>
          </nav>
          {#each active.sections as section (section.id)}
            {@const kind = active.kind}
            <section id={section.id} class="article-section stack">
              <h3>{t(section.title)}</h3>
              {#if definition && kind}
                {#if section.id === 'overview'}<p>{t(definition.description)}</p>{/if}
                {#if section.id === 'connections'}
                  <dl class="connect-list">
                    <div><dt>{t('Input connections')}</dt><dd>
                      {#each kinds.filter((source) => catalog.connections[source].includes(kind)) as source}
                        <span><a href={href(source)}>{t(articles[source].title)}</a> · {t(connectionLabels[connectionKind(catalog, source, kind)])}</span>
                      {:else}{t('None')}{/each}
                    </dd></div>
                    <div><dt>{t('Output connections')}</dt><dd>
                      {#each catalog.connections[kind] as target}
                        <span><a href={href(target)}>{t(articles[target].title)}</a> · {t(connectionLabels[connectionKind(catalog, kind, target)])}</span>
                      {:else}{t('None')}{/each}
                    </dd></div>
                  </dl>
                {:else if section.id === 'configuration'}
                  <dl class="fields">
                    {#each Object.entries(definition.fields) as [key, field] (key)}
                      <div><dt>{t(field.label)}</dt><dd>{field.options?.map(tOption => t(tOption)).join(' · ') ?? `${field.min}–${field.max}`} <span class="muted">· {t('Default')} {t(String(field.default))}</span></dd></div>
                    {:else}<div><dd>{t('No configurable settings.')}</dd></div>{/each}
                  </dl>
                {:else if section.id === 'simulation'}
                  <p><strong>{preciseMoney(definition.daily)}</strong> {t('base daily cost')}</p>
                {/if}
              {/if}
              {#each section.body ?? [] as paragraph}<p>{t(paragraph)}</p>{/each}
              {#if section.diagram}<p class="path-diagram">{t(section.diagram)}</p>{/if}
              {#if requested === 'game-basics' && section.id === 'first-deployment'}
                <ul class="steps">
                  {#each chapters as chapter, index (chapter)}
                    <li><div><strong>{t(chapter)}</strong><p class="muted">{onboarding.filter((step) => step.chapter === index).map((step) => t(step.title)).join(' · ')}</p></div></li>
                  {/each}
                </ul>
              {/if}
            </section>
          {/each}
          <section class="related stack">
            <h3>{t('Related articles')}</h3>
            <ul>
              {#each active.related as id (id)}<li><a href={href(id)}>{t(articles[id].title)} <ArrowRight size={13} /></a></li>{/each}
            </ul>
          </section>
        </article>
      {:else}
        <section class="stack">
          <h2>{t('Browse articles')}</h2>
          <PageColumns balanced columns={3} minWidth="15rem">
            {#each categoriesList as [key, title] (key)}
              <section class="category" id={`category-${key}`}>
                <Panel inset>
                  {#snippet header()}<h3>{t(title)}</h3>{/snippet}
                <ul>
                  {#each byCategory(key) as [id, article] (id)}<li><a href={href(id)}>{t(article.title)}</a></li>{/each}
                </ul>
                </Panel>
              </section>
            {/each}
          </PageColumns>
        </section>
      {/if}
    </div>
  </div>
</div>

<Slideover bind:open={mobileNav} side="start" title={t('Categories')} closeLabel={t('Close dialog')}>
  {@render navigation()}
</Slideover>

<style>
  .guide { display: grid; gap: 15px; min-width: 0; }
  .guide-header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 16px; background: var(--rail); border: 1px solid var(--border); border-radius: 10px; }
  .guide-header :global(.categories-button) { display: none; }
  .search { width: min(100%, 410px); color: var(--muted); }
  .search :global(input) { min-width: 0; width: 100%; }
  .guide-layout.article-open { display: grid; grid-template-columns: minmax(178px, 235px) minmax(0, 1fr); align-items: start; gap: 16px; }
  .guide-nav { display: grid; gap: 6px; }
  .guide-sidebar { position: sticky; top: 78px; max-height: calc(100dvh - 90px); overflow-y: auto; padding: 4px; }
  .guide-nav a { display: block; padding: 6px 8px; border-radius: 5px; font-size: 13px; }
  a:hover { text-decoration: underline; }
  .guide-nav a[aria-current] { background: var(--tint); color: var(--primary); }
  .guide-content { min-width: 0; }
  .guide-content :is(article, section) { scroll-margin-top: 76px; }
  ul, dl { margin: 0; padding: 0; }
  ul { list-style: none; }
  h2 { margin: 0; }
  .breadcrumbs { color: var(--muted); font-size: 12px; }
  .breadcrumbs a, .article-section a, .toc a, .related a, .category a { color: var(--primary); }
  .toc { border-inline-start: 2px solid var(--primary); background: var(--rail); padding: 10px 14px; }
  .toc ul { margin-top: 5px; columns: 2 168px; }
  .toc li { padding-block: 3px; break-inside: avoid; font-size: 13px; }
  .article-section { border-top: 1px solid var(--border); padding-top: 14px; max-width: 83ch; }
  .article-section p { line-height: 1.65; }
  .fields, .connect-list { display: grid; gap: 8px; }
  .fields > div, .connect-list > div { display: grid; grid-template-columns: minmax(150px, .8fr) minmax(0, 1fr); gap: 8px; padding: 7px 9px; background: var(--rail); border-radius: 6px; }
  dt { font-weight: 600; }
  dd { margin: 0; }
  .connect-list dd span { display: block; }
  .related ul { display: flex; flex-wrap: wrap; gap: 8px; }
  .related a { display: flex; align-items: center; gap: 7px; padding: 6px 11px; border: 1px solid var(--border); border-radius: 7px; font-size: 13px; }
  .related { border-top: 1px solid var(--border); padding-top: 14px; }
  .path-diagram { padding: 12px; background: var(--rail); border: 1px solid var(--border); border-radius: 8px; color: var(--primary); }
  .result-list { display: grid; gap: 8px; }
  .result-list a { display: grid; gap: 3px; padding: 10px 12px; background: var(--rail); border: 1px solid var(--border); border-radius: 8px; }
  .result-list small { color: var(--muted); }
  .category a { display: block; padding-block: 4px; }
  .category li + li { margin-top: 5px; }
  .steps { display: grid; gap: 8px; list-style: none; margin: 0; padding: 0; }
  .steps li { padding: 8px; }
  @media (max-width: 780px) {
    .guide-layout.article-open { grid-template-columns: 1fr; }
    .guide-sidebar { display: none; }
    .guide-header :global(.categories-button) { display: inline-flex; }
    .search { width: auto; flex: 1 1 155px; }
  }
  @media (max-width: 450px) {
    .fields > div, .connect-list > div { grid-template-columns: 1fr; gap: 3px; }
  }
</style>
