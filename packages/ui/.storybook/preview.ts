import type { Preview } from '@storybook/svelte-vite';
import { create } from 'storybook/theming';
import { untrack } from 'svelte';
import '@service-unavailable/ui/theme.css';
import './preview.css';
import { setLocale } from '../stories/copy.svelte';

const preview: Preview = {
  initialGlobals: { locale: 'en' },
  globalTypes: {
    locale: {
      name: 'Language',
      toolbar: { icon: 'globe', items: [{ value: 'en', title: 'English' }, { value: 'ru', title: 'Русский' }] }
    }
  },
  decorators: [
    (story, context) => {
      untrack(() => setLocale(context.globals.locale));
      return story();
    }
  ],
  parameters: {
    layout: 'padded',
    backgrounds: { disable: true },
    docs: { theme: create({ base: 'dark', appContentBg: '#111519', textColor: '#ecf4f2' }) },
    a11y: { test: 'error' },
    options: { storySort: { order: ['Design system', 'Patterns', 'Inputs', 'Navigation', 'Overlays', 'Data', 'Layout'] } }
  }
};

export default preview;
