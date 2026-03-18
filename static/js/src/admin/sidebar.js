import { ref } from 'vue';
import { apiFetch } from '../api.js';

export const sidebarData = ref(null);
export const sidebarLoading = ref(false);
export const sidebarError = ref('');

export async function loadSidebar() {
    sidebarLoading.value = true;
    sidebarError.value = '';
    try {
        const response = await apiFetch('/api/admin/sidebar');
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Ошибка загрузки боковой панели');
        }
        sidebarData.value = await response.json();
    } catch (e) {
        sidebarError.value = e.message;
        console.error('Sidebar load failed', e);
    } finally {
        sidebarLoading.value = false;
    }
}