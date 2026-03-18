import { ref } from 'vue';
import { apiFetch } from '../api.js';
import { showNotification } from './notification.js';

export const settingsData = ref({});
export const settingsLoading = ref(false);
export const settingsSaving = ref(false);
export const settingsError = ref('');

export async function loadSettings() {
    settingsLoading.value = true;
    settingsError.value = '';
    try {
        const response = await apiFetch('/api/admin/settings');
        if (!response.ok) throw new Error('Ошибка загрузки настроек');
        settingsData.value = await response.json();
    } catch (e) {
        settingsError.value = e.message;
    } finally {
        settingsLoading.value = false;
    }
}

export async function saveSettings() {
    settingsSaving.value = true;
    settingsError.value = '';
    try {
        const response = await apiFetch('/api/admin/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settingsData.value)
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Ошибка сохранения');
        }
        showNotification('Настройки сохранены', 'success');
    } catch (e) {
        settingsError.value = e.message;
    } finally {
        settingsSaving.value = false;
    }
}

export function resetSettings() {
    if (confirm('Сбросить все изменения?')) loadSettings();
}