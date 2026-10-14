import { datafluxRum } from '@cloudcare/browser-rum';

datafluxRum.init({
  applicationId: 'type-check-only',
  datakitOrigin: 'https://example.invalid',
});
