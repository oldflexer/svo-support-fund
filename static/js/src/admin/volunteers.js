import { ref, computed } from 'vue';
import { apiFetch } from '../api.js';
import { showNotification } from './notification.js';

export const volunteerStatusFilter = ref('');

export const filteredVolunteers = computed(() => {
    if (!volunteerStatusFilter.value) return volunteers.value.items;
    return volunteers.value.items.filter(v => v.status === volunteerStatusFilter.value);
});

export async function updateVolunteerStatus(id, status, loadSidebar) {
    try {
        const response = await apiFetch(`/api/admin/volunteers/${id}`, {
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