const { createApp, ref, reactive, onMounted, computed } = Vue;

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
        
        // Stats
        const stats = ref({ donations: { total: 0, total_amount: 0 }, volunteers: { total: 0 } });
        
        // Chart ref
        const donationsChart = ref(null);
        let chartInstance = null;

        // Computed
        const filteredDonations = computed(() => {
            if (!donationStatusFilter.value) return donations.value.items;
            return donations.value.items.filter(d => d.status === donationStatusFilter.value);
        });

        const roleLabels = {
            admin: 'Администратор',
            moderator: 'Модератор'
        };

        // Methods
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
            await fetch('/api/auth/logout', { method: 'POST', headers: authHeaders() });
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            isAuthenticated.value = false;
            currentUser.value = {};
        };

        const authHeaders = () => {
            const token = localStorage.getItem('access_token');
            return token ? { 'Authorization': `Bearer ${token}` } : {};
        };

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
                const response = await fetch('/api/dashboard', { headers: authHeaders() });
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
                const url = `/api/donations?page=${page}`;
                const response = await fetch(url, { headers: authHeaders() });
                const data = await response.json();
                donations.value = data;
            } catch (e) {
                console.error(e);
            }
        };

        const loadVolunteers = async (page = 1) => {
            try {
                const url = `/api/volunteers?page=${page}`;
                const response = await fetch(url, { headers: authHeaders() });
                const data = await response.json();
                volunteers.value = data;
            } catch (e) {
                console.error(e);
            }
        };

        const loadAdminUsers = async () => {
            try {
                const response = await fetch('/api/admin/users', { headers: authHeaders() });
                const data = await response.json();
                adminUsers.value = data;
            } catch (e) {
                console.error(e);
            }
        };

        const updateDonationStatus = async (id, status) => {
            try {
                await fetch(`/api/donations/${id}`, {
                    method: 'PUT',
                    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status })
                });
                showNotification('Статус обновлен');
            } catch (e) {
                showNotification('Ошибка', 'error');
            }
        };

        const setActiveTab = (tab) => {
            activeTab.value = tab;
            if (tab === 'donations') loadDonations();
            if (tab === 'volunteers') loadVolunteers();
            if (tab === 'users') loadAdminUsers();
            if (tab === 'dashboard') loadDashboard();
        };

        const getTabTitle = () => {
            const map = {
                dashboard: 'Панель управления',
                donations: 'Пожертвования',
                volunteers: 'Волонтёры',
                users: 'Администраторы',
                stats: 'Статистика',
                audit: 'Логи действий',
                settings: 'Настройки'
            };
            return map[activeTab.value] || 'Админ панель';
        };

        const getTabDescription = () => {
            const map = {
                dashboard: 'Общая статистика и последние действия',
                donations: 'Управление входящими пожертвованиями',
                volunteers: 'Заявки волонтёров',
                users: 'Управление администраторами и модераторами'
            };
            return map[activeTab.value] || '';
        };

        const showNotification = (message, type = 'success') => {
            notification.message = message;
            notification.type = type;
            notification.icon = type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle';
            notification.show = true;
            setTimeout(() => notification.show = false, 3000);
        };

        const formatCurrency = (value) => {
            return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', minimumFractionDigits: 0 }).format(value);
        };

        const formatDate = (iso) => {
            if (!iso) return '';
            const d = new Date(iso);
            return d.toLocaleString('ru-RU');
        };

        // 2FA methods
        const setupTwoFactor = async () => {
            try {
                const response = await fetch('/api/auth/2fa/setup', {
                    method: 'POST',
                    headers: authHeaders()
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
                const response = await fetch('/api/auth/2fa/enable', {
                    method: 'POST',
                    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: twoFactorForm.token })
                });
                if (response.ok) {
                    showNotification('2FA успешно включена');
                    twoFactorModal.value = false;
                    twoFactorForm.token = '';
                    // Refresh user data
                    const userResp = await fetch('/api/auth/me', { headers: authHeaders() });
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
                const response = await fetch('/api/auth/2fa/disable', {
                    method: 'POST',
                    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
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
                const response = await fetch('/api/auth/2fa/backup-codes', {
                    method: 'POST',
                    headers: authHeaders()
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

        // Check existing token on mount
        onMounted(() => {
            const token = localStorage.getItem('access_token');
            if (token) {
                // Validate token
                fetch('/api/auth/me', { headers: authHeaders() })
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
            isAuthenticated,
            currentUser,
            loginForm,
            loginError,
            loading,
            twoFactorModal,
            twoFactorStep,
            twoFactorData,
            twoFactorForm,
            activeTab,
            notification,
            donations,
            volunteers,
            adminUsers,
            recentDonations,
            stats,
            donationStatusFilter,
            filteredDonations,
            donationsChart,
            roleLabels,
            login,
            logout,
            refreshToken,
            verifyTwoFactor,
            setActiveTab,
            updateDonationStatus,
            getTabTitle,
            getTabDescription,
            formatCurrency,
            formatDate,
            showNotification,
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