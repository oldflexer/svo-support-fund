import { ref } from 'vue';
import { apiFetch } from '../api.js';
import { showNotification } from './notification.js';

export async function updateDonationStatus(id, status, loadSidebar) {
    try {
        const response = await apiFetch(`/api/admin/donations/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || 'Ошибка при обновлении статуса');
        }
        loadSidebar?.();
        showNotification('Статус обновлен');
    } catch (e) {
        showNotification(e.message, 'error');
    }
}