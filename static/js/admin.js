const { createApp, ref, reactive, onMounted, computed, watch } = Vue;

const app = createApp({
    delimiters: ['${', '}'],
    setup() {
        // Auth state
        const isAuthenticated = ref(false);
        const currentUser = ref({});
        const loginForm = reactive({ username: '', password: '' });
        const loginError = ref('');
        const loading = ref(false);
        
        // Two-factor state
        const twoFactorModal = ref(false);
        const twoFactorStep = ref('setup'); // setup, enable, verify, disable
        const twoFactorData = ref({});
        const twoFactorForm = reactive({
            token: '',
            useBackup: false,
            password: ''
        });

        // New user modal
        const showUserModal = ref(false);
        const userLoading = ref(false);
        const userError = ref('');
        const userForm = reactive({
            username: '',
            email: '',
            full_name: '',
            password: '',
            role: 'moderator',
            is_active: true
        });
        
        // Edit user modal
        const editUserModal = ref(false);
        const editingUserId = ref(null);
        
        // UI state
        const activeTab = ref('dashboard');
        const notification = reactive({ show: false, type: 'success', icon: '', message: '' });
        
        // Data tables
        const donations = ref({ items: [], total: 0, page: 1, pages: 1 });
        const volunteers = ref({ items: [], total: 0, page: 1, pages: 1 });
        const adminUsers = ref([]);
        const recentDonations = ref([]);
        
        // Filters
        const donationStatusFilter = ref('');
        const volunteerStatusFilter = ref('');

        // Stats
        const stats = ref({ donations: { total: 0, total_amount: 0, change: 0, total_new_donations: 0 }, volunteers: { total: 0 }});
        
        // Chart ref
        const donationsChart = ref(null);
        let chartInstance = null;

        // Computed
        // const filteredDonations = computed(() => {
        //     if (!donationStatusFilter.value) return donations.value.items;
        //     return donations.value.items.filter(d => d.status === donationStatusFilter.value);
        // });

        const filteredVolunteers = computed(() => {
            if (!volunteerStatusFilter.value) return volunteers.value.items;
            return volunteers.value.items.filter(v => v.status === volunteerStatusFilter.value);
        });

        const roleLabels = {
            admin: 'Администратор',
            moderator: 'Модератор'
        };

        // Methods
        const apiFetch = async (url, options = {}) => {
            // Добавляем текущий access token
            let accessToken = localStorage.getItem('access_token');
            if (accessToken) {
                options.headers = {
                    ...options.headers,
                    'Authorization': `Bearer ${accessToken}`
                };
            }

            let response = await fetch(url, options);

            // Если ответ не 401, возвращаем его
            if (response.status !== 401) {
                return response;
            }

            // Пытаемся обновить токен
            const refreshToken = localStorage.getItem('refresh_token');
            if (!refreshToken) {
                logout();
                throw new Error('Отсутствует refresh token');
            }

            try {
                const refreshResponse = await fetch('/api/auth/refresh', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${refreshToken}` }
                });

                if (!refreshResponse.ok) {
                    logout();
                    throw new Error('Не удалось обновить токен');
                }

                const data = await refreshResponse.json();
                localStorage.setItem('access_token', data.access_token);

                // Повторяем исходный запрос с новым токеном
                options.headers['Authorization'] = `Bearer ${data.access_token}`;
                return await fetch(url, options);
            } catch (e) {
                logout();
                throw e;
            }
        };

        const login = async () => {
            loading.value = true;
            loginError.value = '';
            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(loginForm)
                });
                const data = await response.json();
                if (!response.ok) {
                    loginError.value = data.error || 'Ошибка входа';
                    return;
                }
                if (data.requires_2fa) {
                    twoFactorData.value = { temp_token: data.temp_token, username: data.username };
                    twoFactorStep.value = 'verify';
                    twoFactorModal.value = true;
                    return;
                }
                // Store tokens
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                currentUser.value = data.user;
                isAuthenticated.value = true;
                // Load initial data
                loadDashboard();
            } catch (e) {
                loginError.value = 'Ошибка сети';
            } finally {
                loading.value = false;
            }
        };

        const verifyTwoFactor = async () => {
            loading.value = true;
            try {
                const response = await fetch('/api/auth/verify-2fa', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        temp_token: twoFactorData.value.temp_token,
                        token: twoFactorForm.token,
                        use_backup: twoFactorForm.useBackup
                    })
                });
                const data = await response.json();
                if (!response.ok) {
                    showNotification(data.error || 'Ошибка подтверждения', 'error');
                    return;
                }
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                currentUser.value = data.user;
                isAuthenticated.value = true;
                twoFactorModal.value = false;
                twoFactorForm.token = '';
                twoFactorForm.useBackup = false;
                loadDashboard();
            } catch (e) {
                showNotification('Ошибка сети', 'error');
            } finally {
                loading.value = false;
            }
        };

        const logout = async () => {
            await apiFetch('/api/auth/logout', {method: 'POST'});
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            isAuthenticated.value = false;
            currentUser.value = {};
            showNotification('Сессия истекла. Пожалуйста, войдите снова.', 'warning');
        };

        // const authHeaders = () => {
        //     const token = localStorage.getItem('access_token');
        //     return token ? { 'Authorization': `Bearer ${token}` } : {};
        // };

        const refreshToken = async () => {
            const refresh = localStorage.getItem('refresh_token');
            if (!refresh) return;
            try {
                const response = await fetch('/api/auth/refresh', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${refresh}` }
                });
                const data = await response.json();
                if (response.ok) {
                    localStorage.setItem('access_token', data.access_token);
                }
            } catch (e) {
                console.error('Refresh failed', e);
            }
        };

        const loadDashboard = async () => {
            try {
                const response = await apiFetch('/api/dashboard');
                const data = await response.json();
                stats.value = {
                    donations: data.donations,
                    volunteers: data.volunteers
                };
                recentDonations.value = data.recent_donations;
                // Update chart
                if (donationsChart.value) {
                    if (chartInstance) chartInstance.destroy();
                    const ctx = donationsChart.value.getContext('2d');
                    chartInstance = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: data.chart.labels,
                            datasets: [{
                                label: 'Сумма пожертвований',
                                data: data.chart.datasets[0].data,
                                borderColor: 'rgb(59, 130, 246)',
                                tension: 0.1
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: true
                        }
                    });
                }
            } catch (e) {
                console.error('Dashboard load failed', e);
            }
        };

        const loadDonations = async (page = 1) => {
            try {
                let url = `/api/donations?page=${page}`;
                if (donationStatusFilter.value) {
                    url += `&status=${encodeURIComponent(donationStatusFilter.value)}`;
                }
                const response = await apiFetch(url);
                const data = await response.json();
                donations.value = data;
            } catch (e) {
                console.error(e);
            }
        };

        const prevDonationsPage = () => {
            if (donations.value.page > 1) {
                loadDonations(donations.value.page - 1);
            }
        };

        const nextDonationsPage = () => {
            if (donations.value.page < donations.value.pages) {
                loadDonations(donations.value.page + 1);
            }
        };

        watch(donationStatusFilter, () => {
            loadDonations(1);
        });

        const loadVolunteers = async (page = 1) => {
            try {
                const url = `/api/volunteers?page=${page}`;
                if (volunteerStatusFilter.value) {
                    url += `&status=${encodeURIComponent(volunteerStatusFilter.value)}`;
                }
                const response = await apiFetch(url);
                const data = await response.json();
                volunteers.value = data;
            } catch (e) {
                console.error(e);
            }
        };

        const prevVolunteersPage = () => {
            if (volunteers.value.page > 1) {
                loadVolunteers(donations.value.page - 1);
            }
        };

        const nextVolunteersPage = () => {
            if (volunteers.value.page < volunteers.value.pages) {
                loadVolunteers(volunteers.value.page + 1);
            }
        };

        watch(volunteerStatusFilter, () => {
            loadVolunteers(1);
        });

        const loadAdminUsers = async () => {
            try {
                const response = await apiFetch('/api/admin/users');
                const data = await response.json();
                adminUsers.value = data;
            } catch (e) {
                console.error(e);
            }
        };

        const updateDonationStatus = async (id, status) => {
            try {
                const response = await apiFetch(`/api/donations/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status })
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || 'Ошибка при обновлении статуса');
                }

                loadDashboard()
                loadDonations(donations.value.page)

                showNotification('Статус обновлен');
                
            } catch (e) {
                showNotification('Ошибка', 'error');
            }
        };

        const updateVolunteerStatus = async (id, status) => {
            try {
                const response = await apiFetch(`/api/volunteers/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status })
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || 'Ошибка при обновлении статуса');
                }

                loadDashboard()
                loadVolunteers()

                showNotification('Статус обновлен');

            } catch (e) {
                showNotification('Ошибка', 'error');
            }
        };

        const createUser = async () => {
            userLoading.value = true;
            userError.value = '';
            try {
                const response = await apiFetch('/api/admin/users', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(userForm)
                });
                const data = await response.json();
                if (!response.ok) {
                    userError.value = data.error || 'Ошибка при создании пользователя';
                    return;
                }
                showNotification('Пользователь успешно создан', 'success');
                showUserModal.value = false;
                // Сброс формы
                resetUserForm();
                // Обновить список пользователей, если активна вкладка users
                if (activeTab.value === 'users') {
                    loadAdminUsers();
                }
            } catch (e) {
                userError.value = 'Ошибка сети';
            } finally {
                userLoading.value = false;
            }
        };

        const resetUserForm = () => {
            userForm.username = '';
            userForm.email = '';
            userForm.full_name = '';
            userForm.password = '';
            userForm.role = 'moderator';
            userForm.is_active = true;
            userError.value = '';
        };

        const editUser = (user) => {
            editUserModal.value = true;
            editingUserId.value = user.id;
            userError.value = '';
            
            userForm.username = user.username;
            userForm.email = user.email;
            userForm.full_name = user.full_name || '';
            userForm.password = '';
            userForm.role = user.role;
            userForm.is_active = user.is_active;
        };

        const closeEditUserModal = () => {
            editUserModal.value = false;
            resetUserForm();
        };

        const saveUser = async () => {
            userLoading.value = true;
            userError.value = '';
            try {
                const response = await apiFetch(`/api/admin/users/${editingUserId.value}`, {
                    method: 'PUT',
                    body: JSON.stringify(userForm)
                });
                const data = await response.json();
                if (!response.ok) {
                    userError.value = data.error || 'Ошибка при сохранении пользователя';
                    return;
                }

                showNotification('Пользователь обновлен', 'success');
                editUserModal.value = false;

                // deleteUser(editingUserId)
                editingUserId.value = null;

                resetUserForm();

                if (activeTab.value === 'users') {
                    loadAdminUsers();
                }

            } catch (e) {
                userError.value = 'Ошибка сети';
            } finally {
                userLoading.value = false;
            }
        };

        const confirmDeleteUser = () => {
            if (confirm('Вы уверены, что хотите удалить этого пользователя?')) {
                deleteUser(editingUserId.value);
            }
        };

        const deleteUser = async (userId) => {

            userLoading.value = true;
            userError.value = '';

            try {
                const response = await apiFetch(`/api/admin/users/${userId}`, {
                    method: 'DELETE'
                });

                const data = await response.json();
                if (!response.ok) {
                    userError.value = data.error || 'Ошибка при удалении пользователя';
                    return;
                }

                showNotification('Пользователь удалён', 'success');

                closeEditUserModal()
                
                if (activeTab.value === 'users') {
                    loadAdminUsers();
                }

            } catch (e) {
                userError.value = 'Ошибка сети';
            } finally {
                userLoading.value = false;
            }
        };

        const setActiveTab = (tab) => {
            activeTab.value = tab;
            if (tab === 'dashboard') loadDashboard();
            if (tab === 'stats') loadStats();
            if (tab === 'donations') loadDonations(1);
            if (tab === 'volunteers') loadVolunteers();
            if (tab === 'users') loadAdminUsers();
            if (tab === 'audit') loadAudit();
            if (tab === 'settings') loadSettings();
        };

        const getTabTitle = () => {
            const map = {
                dashboard: 'Панель управления',
                stats: 'Статистика',
                donations: 'Пожертвования',
                volunteers: 'Волонтёры',
                users: 'Администраторы',
                audit: 'Логи действий',
                settings: 'Настройки'
            };
            return map[activeTab.value] || 'Админ панель';
        };

        const getTabDescription = () => {
            const map = {
                dashboard: 'Общая статистика и последние действия',
                stats: 'Статистика',
                donations: 'Управление входящими пожертвованиями',
                volunteers: 'Заявки волонтёров',
                users: 'Управление администраторами и модераторами',
                audit: 'Логи действий',
                settings: 'Настройки'
            };
            return map[activeTab.value] || '';
        };

        const showNotification = (message, type = 'success') => {
            notification.message = message;
            notification.type = type;
            notification.icon = type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle';
            notification.show = true;
            setTimeout(() => notification.show = false, 5000);
        };

        const formatCurrency = (value) => {
            return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', minimumFractionDigits: 0 }).format(value);
        };

        const formatPercent = (value) => {
            return new Intl.NumberFormat('ru-RU', { style: 'percent', minimumFractionDigits: 0 }).format(value);
        };

        const formatDate = (iso) => {
            if (!iso) return '';
            const d = new Date(iso);
            return d.toLocaleString('ru-RU');
        };

        // 2FA methods
        const setupTwoFactor = async () => {
            try {
                const response = await apiFetch('/api/auth/2fa/setup', {
                    method: 'POST'
                });
                const data = await response.json();
                twoFactorData.value = data;
                twoFactorStep.value = 'setup';
                twoFactorModal.value = true;
            } catch (e) {
                showNotification('Ошибка загрузки 2FA', 'error');
            }
        };

        const enableTwoFactor = async () => {
            try {
                const response = await apiFetch('/api/auth/2fa/enable', {
                    method: 'POST',
                    body: JSON.stringify({ token: twoFactorForm.token })
                });
                if (response.ok) {
                    showNotification('2FA успешно включена');
                    twoFactorModal.value = false;
                    twoFactorForm.token = '';
                    // Refresh user data
                    const userResp = await apiFetch('/api/auth/me');
                    currentUser.value = await userResp.json();
                } else {
                    const err = await response.json();
                    showNotification(err.error || 'Ошибка', 'error');
                }
            } catch (e) {
                showNotification('Ошибка сети', 'error');
            }
        };

        const disableTwoFactor = async () => {
            try {
                const response = await apiFetch('/api/auth/2fa/disable', {
                    method: 'POST',
                    body: JSON.stringify({
                        password: twoFactorForm.password,
                        token: twoFactorForm.token
                    })
                });
                if (response.ok) {
                    showNotification('2FA отключена');
                    twoFactorModal.value = false;
                    twoFactorForm.password = '';
                    twoFactorForm.token = '';
                } else {
                    const err = await response.json();
                    showNotification(err.error || 'Ошибка', 'error');
                }
            } catch (e) {
                showNotification('Ошибка сети', 'error');
            }
        };

        const regenerateBackupCodes = async () => {
            try {
                const response = await apiFetch('/api/auth/2fa/backup-codes', {
                    method: 'POST'
                });
                const data = await response.json();
                twoFactorData.value.backup_codes = data.backup_codes;
                showNotification('Новые резервные коды сгенерированы');
            } catch (e) {
                showNotification('Ошибка', 'error');
            }
        };

        const copyToClipboard = (text) => {
            navigator.clipboard.writeText(text).then(() => {
                showNotification('Скопировано');
            }).catch(() => {
                showNotification('Ошибка копирования', 'error');
            });
        };

        const downloadBackupCodes = () => {
            const codes = twoFactorData.value.backup_codes.join('\n');
            const blob = new Blob([codes], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'backup_codes.txt';
            a.click();
            URL.revokeObjectURL(url);
        };

        // Check permission
        const hasPermission = (roles) => {
            return roles.includes(currentUser.value.role);
        };

        // Check existing token on mount
        onMounted(() => {
            const token = localStorage.getItem('access_token');
            if (token) {
                // Validate token
                apiFetch('/api/auth/me')
                    .then(res => res.ok ? res.json() : Promise.reject())
                    .then(user => {
                        currentUser.value = user;
                        isAuthenticated.value = true;
                        loadDashboard();
                    })
                    .catch(() => {
                        localStorage.removeItem('access_token');
                        localStorage.removeItem('refresh_token');
                    });
            }
        });

        return {
            // States
            isAuthenticated,
            currentUser,
            loginForm,
            loginError,
            loading,
            twoFactorModal,
            twoFactorStep,
            twoFactorData,
            twoFactorForm,
            showUserModal,
            userLoading,
            userError,
            userForm,
            editUserModal,
            editingUserId,
            activeTab,
            notification,
            donations,
            volunteers,
            adminUsers,
            recentDonations,
            stats,
            donationStatusFilter,
            volunteerStatusFilter,
            donationsChart,

            // Computed
            // filteredDonations,
            filteredVolunteers,
            
            // Constants
            roleLabels,

            // Methods
            apiFetch,
            login,
            logout,
            refreshToken,
            verifyTwoFactor,
            prevDonationsPage,
            nextDonationsPage,
            prevVolunteersPage,
            nextVolunteersPage,
            updateDonationStatus,
            updateVolunteerStatus,
            createUser,
            resetUserForm,
            editUser,
            closeEditUserModal,
            saveUser,
            confirmDeleteUser,
            deleteUser,
            setActiveTab,
            getTabTitle,
            getTabDescription,
            formatCurrency,
            formatPercent,
            formatDate,
            showNotification,
            hasPermission,

            // 2FA
            setupTwoFactor,
            enableTwoFactor,
            disableTwoFactor,
            regenerateBackupCodes,
            copyToClipboard,
            downloadBackupCodes
        };
    }
});

app.mount('#admin-app');