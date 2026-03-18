import { ref } from 'vue';
import { apiFetch } from '../api.js';

export const statsData = ref(null);
export const statsLoading = ref(false);
export const statsError = ref('');

export async function loadStats() {
    statsLoading.value = true;
    statsError.value = '';
    try {
        const response = await apiFetch('/api/admin/stats');
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Ошибка загрузки статистики');
        }
        statsData.value = await response.json();
    } catch (e) {
        statsError.value = e.message;
        console.error('Stats load failed', e);
    } finally {
        statsLoading.value = false;
    }
}