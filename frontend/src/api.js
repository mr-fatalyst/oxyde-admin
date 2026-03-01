/**
 * Detect the base path where the admin is mounted.
 *
 * Uses the resolved (absolute) URL from the script tag to extract the path
 * prefix. For example, if the script src resolves to
 * "http://host/admin/assets/index-xxx.js", the base is "/admin/".
 *
 * In dev mode (Vite), there's no matching script tag, so falls back to "/".
 */
function detectBase() {
    const scripts = document.querySelectorAll('script[src]');
    for (const s of scripts) {
        const match = s.src.match(/^https?:\/\/[^/]+(\/.*\/)assets\//);
        if (match) return match[1];
    }
    return '/';
}

export const BASE = detectBase();

/** Base URL of the main application (without the admin mount path). */
export const APP_BASE = BASE.replace(/[^/]+\/$/, '');

const API_PREFIX = BASE.endsWith('/') ? BASE.slice(0, -1) : BASE;

const TOKEN_KEY = 'admin_token';

export class ApiError extends Error {
    constructor(message, status, response) {
        super(message);
        this.status = status;
        this.response = response;
    }
}

const _errorListeners = [];

export function onApiError(callback) {
    _errorListeners.push(callback);
    return () => {
        const idx = _errorListeners.indexOf(callback);
        if (idx !== -1) _errorListeners.splice(idx, 1);
    };
}

export async function api(path, options = {}) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
        options.headers = { ...options.headers, Authorization: `Bearer ${token}` };
    }
    const res = await fetch(API_PREFIX + path, options);
    if (!res.ok) {
        if (res.status === 401) {
            localStorage.removeItem(TOKEN_KEY);
            const { default: router } = await import('@/router.js');
            if (router.currentRoute.value.name !== 'login') {
                router.push('/login');
            }
            throw new ApiError('Unauthorized', 401, res);
        }
        let message = `${res.status} ${res.statusText}`;
        try {
            const body = await res.clone().json();
            if (body.detail) {
                message = typeof body.detail === 'string'
                    ? body.detail
                    : JSON.stringify(body.detail);
            }
        } catch {}
        if (res.status !== 422) {
            for (const cb of _errorListeners) cb(message, res.status);
        }
        throw new ApiError(message, res.status, res);
    }
    return res;
}
