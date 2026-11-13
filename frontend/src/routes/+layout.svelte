<script lang="ts">
  import '@fontsource/inter/latin-400.css';
  import '@fontsource/inter/latin-500.css';
  import '@fontsource/inter/latin-600.css';
  import '@fontsource/inter/latin-700.css';
  import '@fontsource/space-grotesk/latin-500.css';
  import '@fontsource/space-grotesk/latin-700.css';
  import '@fontsource/ibm-plex-mono/latin-400.css';
  import '@fontsource/ibm-plex-mono/latin-600.css';
  import '#lib/theme.css';
  let { children } = $props();
</script>

<svelte:head>
  <title>Service Unavailable</title>
  <meta name="description" content="An infrastructure simulation game." />
  <meta name="theme-color" content="#0c1013" />
  <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
</svelte:head>

{@render children()}
