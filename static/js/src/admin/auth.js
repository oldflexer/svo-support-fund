import { ref, reactive } from 'vue';
import { apiFetch } from '../api.js';
import { showNotification } from './notification.js';

export const isAuthenticated = ref(false);
export const currentUser = ref({});
export const loginForm = reactive({ username: '', password: '' });
export const loginError = ref('');
export const loading = ref(false);

export const twoFactorModal = ref(false);
export const twoFactorStep = ref('setup'); // 'setup', 'verify', 'enable', 'disable'
export const twoFactorData = ref({});
export const twoFactorForm = reactive({ token: '', useBackup: false, password: '' });

export async function login(onSuccess) {
    loading.value = true;
    loginError.value = '';
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(loginForm)
        });
        const data = await response.json();
        if (!response.ok) {
            loginError.value = data.error || 'Ошибка входа';
            return;
        }
        if (data.requires_2fa) {
            twoFactorData.value = { temp_token: data.temp_token, username: data.username };
            twoFactorStep.value = 'verify';
            twoFactorModal.value = true;
            return;
        }
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        currentUser.value = data.user;
        isAuthenticated.value = true;
        onSuccess?.();
    } catch (e) {
        loginError.value = 'Ошибка сети';
    } finally {
        loading.value = false;
    }
}

export async function verifyTwoFactor(onSuccess) {
    loading.value = true;
    try {
        const response = await fetch('/api/auth/2fa/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                temp_token: twoFactorData.value.temp_token,
                token: twoFactorForm.token,
                use_backup: twoFactorForm.useBackup
            })
        });
        const data = await response.json();
        if (!response.ok) {
            showNotification(data.error || 'Ошибка подтверждения', 'error');
            return;
        }
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        currentUser.value = data.user;
        isAuthenticated.value = true;
        twoFactorModal.value = false;
        twoFactorForm.token = '';
        twoFactorForm.useBackup = false;
        onSuccess?.();
    } catch (e) {
        showNotification('Ошибка сети', 'error');
    } finally {
        loading.value = false;
    }
}

export async function logout() {
    await apiFetch('/api/auth/logout', { method: 'POST' });
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    isAuthenticated.value = false;
    currentUser.value = {};
    showNotification('Сессия истекла. Пожалуйста, войдите снова.', 'warning');
}

export async function refreshToken() {
    const refresh = localStorage.getItem('refresh_token');
    if (!refresh) return;
    try {
        const response = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${refresh}` }
        });
        const data = await response.json();
        if (response.ok) localStorage.setItem('access_token', data.access_token);
    } catch (e) { console.error('Refresh failed', e); }
}

export function open2FAModal() {
    if (currentUser.value.two_factor_enabled) {
        twoFactorStep.value = 'disable';
        twoFactorModal.value = true;
    } else {
        setupTwoFactor();
    }
}

export async function setupTwoFactor() {
    try {
        const response = await apiFetch('/api/auth/2fa/setup', { method: 'POST' });
        const data = await response.json();
        twoFactorData.value = data;
        twoFactorStep.value = 'setup';
        twoFactorModal.value = true;
    } catch (e) {
        showNotification('Ошибка загрузки 2FA', 'error');
    }
}

export async function enableTwoFactor() {
    try {
        const response = await apiFetch('/api/auth/2fa/enable', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: twoFactorForm.token })
        });
        if (response.ok) {
            showNotification('2FA успешно включена');
            twoFactorModal.value = false;
            twoFactorForm.token = '';
            const userResp = await apiFetch('/api/auth/me');
            currentUser.value = await userResp.json();
        } else {
            const err = await response.json();
            showNotification(err.error || 'Ошибка', 'error');
        }
    } catch (e) {
        showNotification('Ошибка сети', 'error');
    }
}

export async function disableTwoFactor() {
    try {
        const response = await apiFetch('/api/auth/2fa/disable', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                password: twoFactorForm.password,
                token: twoFactorForm.token
            })
        });
        if (response.ok) {
            showNotification('2FA отключена');
            twoFactorModal.value = false;
            twoFactorForm.password = '';
            twoFactorForm.token = '';
            const userResp = await apiFetch('/api/auth/me');
            currentUser.value = await userResp.json();
        } else {
            const err = await response.json();
            showNotification(err.error || 'Ошибка', 'error');
        }
    } catch (e) {
        showNotification('Ошибка сети', 'error');
    }
}

export async function regenerateBackupCodes() {
    try {
        const response = await apiFetch('/api/auth/2fa/backup-codes', { method: 'POST' });
        const data = await response.json();
        twoFactorData.value.backup_codes = data.backup_codes;
        showNotification('Новые резервные коды сгенерированы');
    } catch (e) {
        showNotification('Ошибка', 'error');
    }
}

export function downloadBackupCodes() {
    const codes = twoFactorData.value.backup_codes?.join('\n');
    if (!codes) return;
    const blob = new Blob([codes], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'backup_codes.txt';
    a.click();
    URL.revokeObjectURL(url);
}