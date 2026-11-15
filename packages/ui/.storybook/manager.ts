import { addons } from 'storybook/manager-api';
import { create } from 'storybook/theming';

addons.setConfig({
  theme: create({
    base: 'dark',
    brandTitle: 'Service Unavailable UI',
    colorPrimary: '#c7f46c',
    colorSecondary: '#c7f46c',
    appBg: '#0c1013',
    appContentBg: '#111519',
    appBorderColor: '#28343d',
    textColor: '#ecf4f2'
  })
});
