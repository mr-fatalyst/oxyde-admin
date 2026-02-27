<script setup>
import { ref, inject } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { APP_BASE, BASE, api } from '@/api.js';

const logoUrl = BASE + 'favicon.png';

const router = useRouter();
const toast = useToast();
const config = inject('appConfig', {});
const adminTitle = config.title || 'Oxyde Admin';
const loginUrl = config.login_url || null;

const email = ref('');
const password = ref('');
const loading = ref(false);

async function onLogin() {
    if (!loginUrl) {
        toast.add({ severity: 'error', summary: 'Error', detail: 'Login endpoint not configured', life: 5000 });
        return;
    }
    loading.value = true;
    try {
        const url = APP_BASE + loginUrl.replace(/^\//, '');
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email.value, password: password.value }),
        });
        if (!res.ok) {
            let message = 'Invalid credentials';
            try {
                const body = await res.json();
                if (body.detail) message = body.detail;
            } catch {}
            toast.add({ severity: 'error', summary: 'Login failed', detail: message, life: 5000 });
            return;
        }
        const data = await res.json();
        localStorage.setItem('admin_token', data.token);
        // Verify the token actually grants admin access
        const check = await api('/api/models');
        if (!check.ok) {
            localStorage.removeItem('admin_token');
            toast.add({ severity: 'error', summary: 'Access denied', detail: 'You do not have admin permissions', life: 5000 });
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
                        <label for="email" class="block text-surface-900 dark:text-surface-0 text-xl font-medium mb-2">Email</label>
                        <InputText id="email" type="text" placeholder="Email address" class="w-full md:w-[30rem] mb-8" v-model="email" />

                        <label for="password" class="block text-surface-900 dark:text-surface-0 font-medium text-xl mb-2">Password</label>
                        <Password id="password" v-model="password" placeholder="Password" :toggleMask="true" class="mb-8" fluid :feedback="false" />

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
