import { createApp } from 'vue';
import App from './App.vue';
import router from './router.js';
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
        const res = await api('/api/config/');
        if (res.ok) config = await res.json();
    } catch {
        // use defaults
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

    const title = config.title || 'Oxyde Admin';
    document.title = title;
    app.provide('adminTitle', title);

    app.mount('#app');

    applyThemeConfig(config);
}

bootstrap();
