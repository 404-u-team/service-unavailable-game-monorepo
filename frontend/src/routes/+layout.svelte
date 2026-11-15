<script lang="ts">
  import '@fontsource/inter/latin-400.css';
  import '@fontsource/inter/cyrillic-400.css';
  import '@fontsource/inter/latin-500.css';
  import '@fontsource/inter/cyrillic-500.css';
  import '@fontsource/inter/latin-600.css';
  import '@fontsource/inter/cyrillic-600.css';
  import '@fontsource/inter/latin-700.css';
  import '@fontsource/inter/cyrillic-700.css';
  import '@fontsource/space-grotesk/latin-500.css';
  import '@fontsource/space-grotesk/latin-700.css';
  import '@fontsource/ibm-plex-mono/latin-400.css';
  import '@fontsource/ibm-plex-mono/cyrillic-400.css';
  import '@fontsource/ibm-plex-mono/latin-600.css';
  import '@fontsource/ibm-plex-mono/cyrillic-600.css';
  import '@service-unavailable/ui/theme.css';
  import '#lib/theme.css';
  import { onMount } from 'svelte';
  import { setLanguage, t } from '#lib/i18n.svelte.ts';
  onMount(() => setLanguage(localStorage.getItem('workbench-language') === 'ru' ? 'ru' : 'en'));
  let { children } = $props();
</script>

<svelte:head>
  <title>Service Unavailable</title>
  <meta name="description" content={t("An infrastructure simulation game.")} />
  <meta name="theme-color" content="#0c1013" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
</svelte:head>

{@render children()}
