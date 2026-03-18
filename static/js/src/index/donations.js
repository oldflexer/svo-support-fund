import { reactive, ref } from 'vue';
import { fetchStats } from './stats.js';
import { showNotification } from './notification.js';

export const donationForm = reactive({
    name: '', amount: 1000, message: '', is_anonymous: false
});
export const donationLoading = ref(false);
export const showDonationModal = ref(false);
export const selectedDriveId = ref(null);

export async function submitDonation() {
    donationLoading.value = true;
    try {
        const response = await fetch('/api/public/donations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: donationForm.is_anonymous ? 'Аноним' : donationForm.name,
                amount: donationForm.amount,
                message: donationForm.message,
                is_anonymous: donationForm.is_anonymous,
                drive_id: selectedDriveId.value
            })
        });
        if (response.ok) {
            await fetchStats();
            showNotification('Спасибо за ваше пожертвование!', 'success');
            donationForm.name = ''; donationForm.amount = 1000; donationForm.message = '';
            donationForm.is_anonymous = false;
            showDonationModal.value = false;
        } else {
            const err = await response.json();
            showNotification(err.errors || 'Ошибка при отправке', 'error');
        }
    } catch (e) {
        showNotification('Ошибка сети', 'error');
    } finally {
        donationLoading.value = false;
    }
}

export function showDonationForDrive(driveId) {
    showDonationModal.value = true;
}