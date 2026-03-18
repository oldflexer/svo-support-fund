import { ref } from 'vue';
import { apiFetch } from '../api.js';
import { showNotification } from './notification.js';

export const lastNotificationCheck = ref(new Date().toISOString());
export const notificationPollInterval = ref(null);

export async function pollNotifications(loadSidebar) {
    try {
        const response = await apiFetch(`/api/admin/notifications?last_check=${encodeURIComponent(lastNotificationCheck.value)}`);
        if (!response.ok) return;
        const data = await response.json();
        lastNotificationCheck.value = data.server_time;
        if (data.new_donations > 0 || data.new_volunteers > 0) {
            let parts = [];
            if (data.new_donations > 0) parts.push(`${data.new_donations} новых пожертвований`);
            if (data.new_volunteers > 0) parts.push(`${data.new_volunteers} новых заявок волонтёров`);
            showNotification(parts.join(' и '), 'info');
            loadSidebar?.();
        }
    } catch (e) { console.error('Polling error', e); }
}