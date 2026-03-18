import { ref, reactive, computed } from 'vue';
import { apiFetch } from '../api.js';
import { showNotification } from './notification.js';

export const showDriveModal = ref(false);
export const driveModalMode = ref('add');
export const editingDriveId = ref(null);
export const driveForm = reactive({
    title: '', description: '', needs: [], status: 'активен', collected: 0, needed: 0
});
export const driveLoading = ref(false);
export const driveError = ref('');

export const needsText = computed({
    get: () => Array.isArray(driveForm.needs) ? driveForm.needs.join('\n') : '',
    set: (v) => driveForm.needs = v.split('\n').filter(l => l.trim())
});

export function resetDriveForm() {
    driveForm.title = '';
    driveForm.description = '';
    driveForm.needs = [];
    driveForm.status = 'активен';
    driveForm.collected = 0;
    driveForm.needed = 0;
    driveError.value = '';
}

export function openAddDriveModal() {
    driveModalMode.value = 'add';
    editingDriveId.value = null;
    resetDriveForm();
    showDriveModal.value = true;
}

export function editDrive(drive) {
    driveModalMode.value = 'edit';
    editingDriveId.value = drive.id;
    driveForm.title = drive.title;
    driveForm.description = drive.description || '';
    driveForm.needs = drive.needs || [];
    driveForm.status = drive.status;
    driveForm.collected = drive.collected;
    driveForm.needed = drive.needed;
    showDriveModal.value = true;
}

export async function saveDrive(drivesLoader) {
    driveLoading.value = true;
    driveError.value = '';
    try {
        const url = driveModalMode.value === 'add' ? '/api/admin/drives' : `/api/admin/drives/${editingDriveId.value}`;
        const method = driveModalMode.value === 'add' ? 'POST' : 'PUT';
        const response = await apiFetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(driveForm)
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Ошибка сохранения');
        }
        showNotification(driveModalMode.value === 'add' ? 'Сбор создан' : 'Сбор обновлён', 'success');
        showDriveModal.value = false;
        resetDriveForm();
        drivesLoader?.load(drivesLoader.page.value);
    } catch (e) {
        driveError.value = e.message;
    } finally {
        driveLoading.value = false;
    }
}

export function confirmDeleteDrive(driveId, drivesLoader) {
    if (confirm('Вы уверены, что хотите удалить этот сбор?')) {
        deleteDrive(driveId, drivesLoader);
    }
}

export async function deleteDrive(driveId, drivesLoader) {
    try {
        const response = await apiFetch(`/api/admin/drives/${driveId}`, { method: 'DELETE' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Ошибка удаления');
        }
        showNotification('Сбор удалён', 'success');
        drivesLoader?.load(drivesLoader.page.value);
    } catch (e) {
        showNotification(e.message, 'error');
    }
}