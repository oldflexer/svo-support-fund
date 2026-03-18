import { createApp, ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue';
import { apiFetch } from '../api.js';
import { formatCurrency, formatPercent, formatDate, copyToClipboard } from '../utils.js';
import { createPaginatedLoader } from '../pagination.js';
import { notification, showNotification } from './notification.js';

// Импортируем все модули
import * as auth from './auth.js';
import * as dashboard from './dashboard.js';
import * as sidebar from './sidebar.js';
import * as stats from './stats.js';
import * as donations from './donations.js';
import * as drives from './drives.js';
import * as news from './news.js';
import * as volunteers from './volunteers.js';
import * as users from './users.js';
import * as audit from './audit.js';
import * as settings from './settings.js';
import * as notifications from './notifications.js';

const app = createApp({
    delimiters: ['${', '}'],
    setup() {
        // ---- локальные состояния ----
        const activeTab = ref('dashboard');

        // ---- фильтры ----
        const donationStatusFilter = ref('');
        const driveStatusFilter = ref('');
        const volunteerStatusFilter = ref('');
        const newsCategoryFilter = ref('');
        const newsVerifiedFilter = ref('');

        // ---- загрузчики (используют фильтры) ----
        const donationsLoader = createPaginatedLoader('/api/admin/donations', { status: donationStatusFilter }, apiFetch, { perPage: 15 });
        const drivesLoader = createPaginatedLoader('/api/admin/drives', { status: driveStatusFilter }, apiFetch, { perPage: 5 });
        const volunteersLoader = createPaginatedLoader('/api/admin/volunteers', { status: volunteerStatusFilter }, apiFetch, { perPage: 10 });
        const newsLoader = createPaginatedLoader('/api/admin/news', { category: newsCategoryFilter, verified: newsVerifiedFilter }, apiFetch, { perPage: 5 });
        const usersLoader = createPaginatedLoader('/api/admin/users', {}, apiFetch, { perPage: 10 });
        const auditLoader = createPaginatedLoader('/api/admin/audit', { user_id: audit.auditUserId }, apiFetch, { perPage: 15 });

        // ---- computed для волонтёров ----
        const filteredVolunteers = computed(() => {
            if (!volunteerStatusFilter.value) return volunteersLoader.items.value;
            return volunteersLoader.items.value.filter(v => v.status === volunteerStatusFilter.value);
        });

        // ---- функции для шапки ----
        const getTabTitle = () => {
            const map = {
                dashboard: 'Панель управления',
                stats: 'Статистика',
                donations: 'Пожертвования',
                drives: 'Сборы',
                news: 'Новости',
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
                stats: 'Подробная статистика по всем разделам',
                donations: 'Управление входящими пожертвованиями',
                drives: 'Управление сборами',
                news: 'Управление новостной лентой',
                volunteers: 'Управление заявками волонтёров',
                users: 'Управление администраторами и модераторами',
                audit: 'Аудит действий пользователей',
                settings: 'Настройки сайта'
            };
            return map[activeTab.value] || '';
        };

        // ---- функция проверки прав ----
        const hasPermission = (roles) => {
            return roles.includes(auth.currentUser.value?.role);
        };

        // ---- метки ролей ----
        const roleLabels = {
            admin: 'Администратор',
            moderator: 'Модератор'
        };

        // ---- обёртки для функций, которым нужны загрузчики ----
        const saveDrive = () => drives.saveDrive(drivesLoader);
        const confirmDeleteDrive = (id) => drives.confirmDeleteDrive(id, drivesLoader);
        const deleteDrive = (id) => drives.deleteDrive(id, drivesLoader);

        const saveNews = () => news.saveNews(newsLoader);
        const confirmDeleteNews = (id) => news.confirmDeleteNews(id, newsLoader);
        const deleteNews = (id) => news.deleteNews(id, newsLoader);

        const saveUser = () => users.saveUser(usersLoader);
        const confirmDeleteUser = () => users.confirmDeleteUser(users.editingUserId.value, usersLoader);
        const deleteUser = (id) => users.deleteUser(id, usersLoader);
        const toggleUserStatus = (user) => users.toggleUserStatus(user, usersLoader);

        const updateDonationStatus = (id, status) => donations.updateDonationStatus(id, status, sidebar.loadSidebar);

        // ---- активная вкладка ----
        const setActiveTab = (tab) => {
            activeTab.value = tab;
            sidebar.loadSidebar();
            if (tab === 'dashboard') dashboard.loadDashboard();
            else if (tab === 'stats') stats.loadStats();
            else if (tab === 'donations') donationsLoader.load(1);
            else if (tab === 'drives') drivesLoader.load(1);
            else if (tab === 'news') newsLoader.load(1);
            else if (tab === 'volunteers') volunteersLoader.load(1);
            else if (tab === 'users') usersLoader.load(1);
            else if (tab === 'audit') { auditLoader.load(1); usersLoader.load(1); }
            else if (tab === 'settings') settings.loadSettings();
        };

        // ---- следим за статистикой для обновления сайдбара ----
        watch(() => stats.statsData.value?.count_new_donations, () => sidebar.loadSidebar());
        watch(() => stats.statsData.value?.count_active_drives, () => sidebar.loadSidebar());
        watch(() => stats.statsData.value?.count_not_verified_news, () => sidebar.loadSidebar());
        watch(() => stats.statsData.value?.count_new_volunteers, () => sidebar.loadSidebar());

        // ---- инициализация при монтировании ----
        onMounted(() => {
            const token = localStorage.getItem('access_token');
            if (token) {
                apiFetch('/api/auth/me')
                    .then(res => res.ok ? res.json() : Promise.reject())
                    .then(user => {
                        auth.currentUser.value = user;
                        auth.isAuthenticated.value = true;
                        sidebar.loadSidebar();
                        dashboard.loadDashboard();
                    })
                    .catch(() => {
                        localStorage.removeItem('access_token');
                        localStorage.removeItem('refresh_token');
                    });
                notifications.notificationPollInterval.value = setInterval(
                    () => notifications.pollNotifications(sidebar.loadSidebar),
                    30000
                );
                notifications.pollNotifications(sidebar.loadSidebar);
            }
        });

        onUnmounted(() => {
            if (notifications.notificationPollInterval.value) {
                clearInterval(notifications.notificationPollInterval.value);
            }
        });

        // ---- возвращаем всё, что нужно в шаблоне ----
        return {
            // из модулей
            ...auth,
            ...dashboard,
            ...sidebar,
            ...stats,
            ...donations,
            ...drives,
            ...news,
            ...volunteers,
            ...users,
            ...audit,
            ...settings,
            ...notifications,

            // локальные
            activeTab,
            notification,
            setActiveTab,
            getTabTitle,
            getTabDescription,
            hasPermission,
            roleLabels,

            // фильтры
            donationStatusFilter,
            driveStatusFilter,
            volunteerStatusFilter,
            newsCategoryFilter,
            newsVerifiedFilter,

            // загрузчики
            donations: donationsLoader,
            drives: drivesLoader,
            volunteers: volunteersLoader,
            news: newsLoader,
            adminUsers: usersLoader,
            auditLogs: auditLoader,

            // computed
            filteredVolunteers,

            // обёртки для функций с загрузчиками
            saveDrive,
            confirmDeleteDrive,
            deleteDrive,
            saveNews,
            confirmDeleteNews,
            deleteNews,
            saveUser,
            confirmDeleteUser,
            deleteUser,
            toggleUserStatus,
            updateDonationStatus,

            // утилиты
            formatCurrency,
            formatPercent,
            formatDate,
            copyToClipboard
        };
    }
});

// Глобальный обработчик ошибок для отладки
app.config.errorHandler = (err, instance, info) => {
    console.error('Vue global error:', err, info);
};

app.mount('#admin-app');