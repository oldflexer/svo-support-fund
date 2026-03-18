import { reactive, ref } from 'vue';
import { fetchStats } from './stats.js';
import { showNotification } from './notification.js';

export const volunteerForm = reactive({
    name: '', email: '', phone: '', city: '', skills: '', can_deliver: false
});
export const volunteerLoading = ref(false);

export async function submitVolunteer() {
    volunteerLoading.value = true;
    try {
        const response = await fetch('/api/public/volunteers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(volunteerForm)
        });
        if (response.ok) {
            await fetchStats();
            showNotification('Спасибо за желание помочь! Мы свяжемся с вами.', 'success');
            volunteerForm.name = ''; volunteerForm.email = ''; volunteerForm.phone = '';
            volunteerForm.city = ''; volunteerForm.skills = ''; volunteerForm.can_deliver = false;
        } else {
            const err = await response.json();
            showNotification(err.errors || 'Ошибка при отправке', 'error');
        }
    } catch (e) {
        showNotification('Ошибка сети', 'error');
    } finally {
        volunteerLoading.value = false;
    }
}