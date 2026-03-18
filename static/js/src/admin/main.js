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
import * as audit from './audit.js';          // добавлен модуль аудита
import * as settings from './settings.js';
import * as notifications from './notifications.js';

const app = createApp({
    setup() {
        // ---- локальные состояния ----
        const activeTab = ref('dashboard');

        // ---- фильтры ----
        const donationStatusFilter = ref('');
        const driveStatusFilter = ref('');
        const volunteerStatusFilter = ref('');
        const newsCategoryFilter = ref('');
        const newsVerifiedFilter = ref('');
        // Фильтры для аудита теперь в audit.*

        // ---- загрузчики (используют фильтры) ----
        const donationsLoader = createPaginatedLoader('/api/admin/donations', { status: donationStatusFilter }, apiFetch);
        const drivesLoader = createPaginatedLoader('/api/admin/drives', { status: driveStatusFilter }, apiFetch, { perPage: 5 });
        const volunteersLoader = createPaginatedLoader('/api/admin/volunteers', { status: volunteerStatusFilter }, apiFetch);
        const newsLoader = createPaginatedLoader('/api/admin/news', { category: newsCategoryFilter, verified: newsVerifiedFilter }, apiFetch, { perPage: 5 });
        const usersLoader = createPaginatedLoader('/api/admin/users', {}, apiFetch);
        const auditLoader = createPaginatedLoader('/api/admin/audit', { user_id: audit.auditUserId }, apiFetch);

        // ---- computed для волонтёров ----
        const filteredVolunteers = computed(() => {
            if (!volunteerStatusFilter.value) return volunteersLoader.items.value;
            return volunteersLoader.items.value.filter(v => v.status === volunteerStatusFilter.value);
        });

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
            ...audit,          // теперь auditFilters и auditUserId доступны в шаблоне
            ...settings,
            ...notifications,

            // локальные
            activeTab,
            notification,    // глобальный объект уведомлений
            setActiveTab,

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

            // утилиты
            formatCurrency,
            formatPercent,
            formatDate,
            copyToClipboard
        };
    }
});

app.mount('#admin-app');