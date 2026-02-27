import { createApp } from 'vue';
import App from './App.vue';
import router, { setAuthEnabled } from './router.js';
import { api } from '@/api.js';
import { applyThemeConfig, presets } from '@/layout/composables/theme.js';

import Aura from '@primeuix/themes/aura';
import PrimeVue from 'primevue/config';
import ConfirmationService from 'primevue/confirmationservice';
import ToastService from 'primevue/toastservice';

import '@/assets/tailwind.css';
import '@/assets/styles.scss';

async function bootstrap() {
    let config = { title: 'Oxyde Admin', preset: 'Aura', primary_color: 'sky', surface: 'slate' };
    try {
        const res = await api('/api/config');
        if (res.ok) config = await res.json();
    } catch {
        // use defaults
    }

    if (config.auth_enabled) {
        setAuthEnabled(true);
    }

    const app = createApp(App);

    app.use(router);
    app.use(PrimeVue, {
        theme: {
            preset: presets[config.preset] || Aura,
            options: {
                darkModeSelector: '.app-dark',
            },
        },
    });
    app.use(ToastService);
    app.use(ConfirmationService);

    config.title = config.title || 'Oxyde Admin';
    document.title = config.title;
    app.provide('appConfig', config);

    app.mount('#app');

    applyThemeConfig(config);
}

bootstrap();
