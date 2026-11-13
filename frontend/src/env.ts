import { defineEnvVars } from '@sveltejs/kit/env';

export const variables = defineEnvVars({
  CORE_API_URL: {
    description: 'Core API origin as seen by the workbench server.',
    schema: (value) => new URL(value || 'http://127.0.0.1:8000').origin
  }
});
