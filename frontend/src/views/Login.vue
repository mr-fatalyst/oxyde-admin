<script setup>
import { computed, ref, inject } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { APP_BASE, BASE, api } from '@/api.js';

const logoUrl = BASE + 'favicon.png';
const apiBase = BASE.endsWith('/') ? BASE.slice(0, -1) : BASE;

const router = useRouter();
const toast = useToast();
const config = inject('appConfig', {});
const adminTitle = config.title || 'Oxyde Admin';

// config.auth is the current shape; the top-level keys are the pre-0.5 one
const auth = config.auth || {
    enabled: config.auth_enabled,
    login_url: config.login_url,
    builtin_login: false,
    credentials_schema: null,
};
const loginUrl = auth.login_url || null;
const builtinLogin = !!auth.builtin_login;

// Built-in mode: the login form is rendered from the provider's
// credentials_model JSON schema (SecretStr fields become password inputs).
const fields = computed(() => {
    const schema = auth.credentials_schema;
    if (!schema) return [];
    return Object.entries(schema.properties || {}).map(([name, prop]) => ({
        name,
        label: prop.title || name,
        password: prop.format === 'password' || prop.writeOnly === true,
    }));
});

const formData = ref({});
const email = ref('');
const password = ref('');
const loading = ref(false);

async function requestToken() {
    if (builtinLogin) {
        const res = await fetch(apiBase + '/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData.value),
        });
        return res;
    }
    if (!loginUrl) {
        return null;
    }
    const url = APP_BASE + loginUrl.replace(/^\//, '');
    return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.value, password: password.value }),
    });
}

async function onLogin() {
    loading.value = true;
    try {
        const res = await requestToken();
        if (!res) {
            toast.add({ severity: 'error', summary: 'Error', detail: 'Login endpoint not configured', life: 5000 });
            return;
        }
        if (!res.ok) {
            let message = 'Invalid credentials';
            try {
                const body = await res.json();
                if (body.detail) {
                    message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
                }
            } catch {}
            toast.add({ severity: 'error', summary: 'Login failed', detail: message, life: 5000 });
            return;
        }
        const data = await res.json();
        localStorage.setItem('admin_token', data.token);
        // Verify the token actually grants admin access
        try {
            await api('/api/models');
        } catch (e) {
            if (e.status === 401) {
                toast.add({ severity: 'error', summary: 'Access denied', detail: 'You do not have admin permissions', life: 5000 });
            }
            return;
        }
        router.push('/');
    } catch (e) {
        toast.add({ severity: 'error', summary: 'Error', detail: 'Network error', life: 5000 });
    } finally {
        loading.value = false;
    }
}
</script>

<template>
    <div class="bg-surface-50 dark:bg-surface-950 flex items-center justify-center min-h-screen min-w-[100vw] overflow-hidden">
        <div class="flex flex-col items-center justify-center">
            <div style="border-radius: 56px; padding: 0.3rem; background: linear-gradient(180deg, var(--primary-color) 10%, rgba(33, 150, 243, 0) 30%)">
                <div class="w-full bg-surface-0 dark:bg-surface-900 py-20 px-8 sm:px-20" style="border-radius: 53px">
                    <div class="text-center mb-8">
                        <img :src="logoUrl" alt="Logo" style="height: 3rem" class="mb-4 mx-auto" />
                        <div class="text-surface-900 dark:text-surface-0 text-3xl font-medium mb-4">{{ adminTitle }}</div>
                        <span class="text-muted-color font-medium">Sign in to continue</span>
                    </div>

                    <form @submit.prevent="onLogin">
                        <template v-if="builtinLogin">
                            <div v-for="f in fields" :key="f.name">
                                <label :for="'cred-' + f.name" class="block text-surface-900 dark:text-surface-0 text-xl font-medium mb-2">{{ f.label }}</label>
                                <Password
                                    v-if="f.password"
                                    :id="'cred-' + f.name"
                                    v-model="formData[f.name]"
                                    :toggleMask="true"
                                    class="mb-8"
                                    fluid
                                    :feedback="false"
                                />
                                <InputText v-else :id="'cred-' + f.name" type="text" class="w-full md:w-[30rem] mb-8" v-model="formData[f.name]" />
                            </div>
                        </template>
                        <template v-else>
                            <label for="email" class="block text-surface-900 dark:text-surface-0 text-xl font-medium mb-2">Email</label>
                            <InputText id="email" type="text" placeholder="Email address" class="w-full md:w-[30rem] mb-8" v-model="email" />

                            <label for="password" class="block text-surface-900 dark:text-surface-0 font-medium text-xl mb-2">Password</label>
                            <Password id="password" v-model="password" placeholder="Password" :toggleMask="true" class="mb-8" fluid :feedback="false" />
                        </template>

                        <Button type="submit" label="Sign In" class="w-full" :loading="loading" />
                    </form>
                </div>
            </div>
        </div>
    </div>
    <Toast />
</template>

<style scoped>
.pi-eye {
    transform: scale(1.6);
    margin-right: 1rem;
}
.pi-eye-slash {
    transform: scale(1.6);
    margin-right: 1rem;
}
</style>
