import { ref, reactive } from 'vue';
import { apiFetch } from '../api.js';
import { showNotification } from './notification.js';

export const showUserModal = ref(false);
export const userModalMode = ref('add');
export const editingUserId = ref(null);
export const userLoading = ref(false);
export const userError = ref('');
export const userForm = reactive({
    username: '', email: '', full_name: '', password: '', role: 'moderator', is_active: true
});

export function resetUserForm() {
    userForm.username = ''; userForm.email = ''; userForm.full_name = '';
    userForm.password = ''; userForm.role = 'moderator'; userForm.is_active = true;
    userError.value = '';
}

export function openAddUserModal() {
    userModalMode.value = 'add';
    editingUserId.value = null;
    resetUserForm();
    showUserModal.value = true;
}

export function editUser(user) {
    userModalMode.value = 'edit';
    editingUserId.value = user.id;
    userForm.username = user.username;
    userForm.email = user.email;
    userForm.full_name = user.full_name || '';
    userForm.password = '';
    userForm.role = user.role;
    userForm.is_active = user.is_active;
    userError.value = '';
    showUserModal.value = true;
}

export async function saveUser(usersLoader) {
    userLoading.value = true;
    userError.value = '';
    try {
        const url = userModalMode.value === 'add' ? '/api/admin/users' : `/api/admin/users/${editingUserId.value}`;
        const method = userModalMode.value === 'add' ? 'POST' : 'PUT';
        const response = await apiFetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userForm)
        });
        const data = await response.json();
        if (!response.ok) {
            userError.value = data.error || 'Ошибка при сохранении пользователя';
            return;
        }
        showNotification(userModalMode.value === 'add' ? 'Пользователь создан' : 'Пользователь обновлен', 'success');
        showUserModal.value = false;
        resetUserForm();
        if (usersLoader) usersLoader.load(usersLoader.page.value);
    } catch (e) {
        userError.value = 'Ошибка сети';
    } finally {
        userLoading.value = false;
    }
}

export function confirmDeleteUser(editingUserId, usersLoader) {
    if (confirm('Вы уверены, что хотите удалить этого пользователя?')) {
        deleteUser(editingUserId, usersLoader);
    }
}

export async function deleteUser(userId, usersLoader) {
    userLoading.value = true;
    userError.value = '';
    try {
        const response = await apiFetch(`/api/admin/users/${userId}`, { method: 'DELETE' });
        const data = await response.json();
        if (!response.ok) {
            userError.value = data.error || 'Ошибка при удалении пользователя';
            return;
        }
        showNotification('Пользователь удалён', 'success');
        if (usersLoader) {
            if (usersLoader.items.value.length === 0 && usersLoader.page.value > 1) {
                usersLoader.load(usersLoader.page.value - 1);
            } else {
                usersLoader.load(usersLoader.page.value);
            }
        }
        showUserModal.value = false;
    } catch (e) {
        userError.value = 'Ошибка сети';
    } finally {
        userLoading.value = false;
    }
}

export async function toggleUserStatus(user, usersLoader) {
    const action = user.is_active ? 'деактивировать' : 'активировать';
    try {
        const response = await apiFetch(`/api/admin/users/${user.id}/toggle`, { method: 'POST' });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || `Не удалось ${action} пользователя`);
        }
        const result = await response.json();
        showNotification(result.message || `Пользователь успешно ${action}`, 'success');
        if (usersLoader) usersLoader.load(usersLoader.page.value);
    } catch (e) {
        showNotification(e.message, 'error');
    }
}