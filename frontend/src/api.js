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

const API_PREFIX = BASE.endsWith('/') ? BASE.slice(0, -1) : BASE;

const _errorListeners = [];

export function onApiError(callback) {
    _errorListeners.push(callback);
}

export async function api(path, options) {
    const res = await fetch(API_PREFIX + path, options);
    if (!res.ok) {
        let message = `${res.status} ${res.statusText}`;
        try {
            const body = await res.clone().json();
            if (body.detail) {
                message = typeof body.detail === 'string'
                    ? body.detail
                    : JSON.stringify(body.detail);
            }
        } catch {}
        for (const cb of _errorListeners) cb(message, res.status);
    }
    return res;
}
