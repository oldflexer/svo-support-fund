import { logout } from './admin/auth.js';

export async function apiFetch(url, options = {}) {
    let accessToken = localStorage.getItem('access_token');
    if (accessToken) {
        options.headers = {
            ...options.headers,
            'Authorization': `Bearer ${accessToken}`
        };
    }

    let response = await fetch(url, options);

    if (response.status !== 401) {
        return response;
    }

    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
        logout();
        throw new Error('Отсутствует refresh token');
    }

    try {
        const refreshResponse = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${refreshToken}` }
        });

        if (!refreshResponse.ok) {
            logout();
            throw new Error('Не удалось обновить токен');
        }

        const data = await refreshResponse.json();
        localStorage.setItem('access_token', data.access_token);

        options.headers['Authorization'] = `Bearer ${data.access_token}`;
        return await fetch(url, options);
    } catch (e) {
        logout();
        throw e;
    }
}