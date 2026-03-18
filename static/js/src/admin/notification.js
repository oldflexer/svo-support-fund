import { reactive } from 'vue';

export const notification = reactive({ show: false, type: 'success', icon: '', message: '' });

export function showNotification(message, type = 'success') {
    notification.message = message;
    notification.type = type;
    notification.icon = type === 'success' ? 'fas fa-check-circle' 
                        : type === 'error' ? 'fas fa-exclamation-circle' 
                        : 'fas fa-info-circle';
    notification.show = true;
    setTimeout(() => notification.show = false, 5000);
}