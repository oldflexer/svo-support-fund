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

        // Sidebar
        const sidebarData = ref(null);
        const sidebarLoading = ref(false);
        const sidebarError = ref('');

        // Dashboard
        const dashboardData = ref({
            donations: { total: 0, total_amount: 0, change: 0, recent_donations: 0 },
            volunteers: { total: 0 },
            chart: { labels: [], datasets: [{ label: '', data: []}] }
        });

        // Stats
        const statsData = ref(null);
        const statsLoading = ref(false);
        const statsError = ref('');

        // Drives
        const showDriveModal = ref(false);
        const driveModalMode = ref('add'); // 'add' или 'edit'
        const editingDriveId = ref(null);
        const driveForm = reactive({
            title: '',
            description: '',
            needs: [],
            status: 'активен', // активен, завершен, приостановлен
            collected: 0,
            needed: 0
        });
        const driveLoading = ref(false);
        const driveError = ref('');

        const needsText = computed({
            get: () => {
                if (Array.isArray(driveForm.needs)) {
                    return driveForm.needs.join('\n');
                }
                return '';
            },
            set: (value) => {
                driveForm.needs = value.split('\n').filter(line => line.trim() !== '');
            }
        });

        // News
        const news = ref({ items: [], total: 0, page: 1, pages: 1});

        const newsCategoryFilter = ref('');
        const newsVerifiedFilter = ref(''); // 'true', 'false', '' - все

        const showNewsModal = ref(false);
        const newsModalMode = ref('add'); // 'add' или 'edit'
        const editingNewsId = ref(null);
        const newsForm = reactive({
            title: '',
            slug: '',
            excerpt: '',
            content: '',
            category: 'новости',
            is_verified: false,
            main_image: ''
        });
        const newsLoading = ref(false);
        const newsError = ref('');

        const translitMap = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'cz', 'ч': 'ch', 'ш': 'sh', 'щ': 'shh',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
            'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
            'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'J', 'К': 'K', 'Л': 'L', 'М': 'M',
            'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
            'Ф': 'F', 'Х': 'H', 'Ц': 'Cz', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shh',
            'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
            ' ': '-', ',': '', '.': '', '!': '', '?': '', ':': '', ';': '', '"': '',
            "'": '', '(': '', ')': '', '[': '', ']': '', '{': '', '}': '', '/': '',
            '\\': '', '|': '', '@': '', '#': '', '$': '', '%': '', '^': '', '&': '',
            '*': '', '+': '', '=': '', '~': '', '`': '', '<': '', '>': ''
        };

        const slugManuallyEdited = ref(false);

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

        // Settings
        const settingsData = ref({});
        const settingsLoading = ref(false);
        const settingsSaving = ref(false);
        const settingsError = ref('');
        
        // Edit user modal
        const editUserModal = ref(false);
        const editingUserId = ref(null);
        
        // UI state
        const activeTab = ref('dashboard');
        const notification = reactive({ show: false, type: 'success', icon: '', message: '' });
        
        // Data tables
        const donations = ref({ items: [], total: 0, page: 1, pages: 1 });
        const recentDonations = ref([]);
        const drives = ref({ items: [], total: 0, page: 1, pages: 1});
        const volunteers = ref({ items: [], total: 0, page: 1, pages: 1 });
        const adminUsers = ref({ items: [], total: 0, page: 1, pages: 1 });
        const auditLogs = ref({ items: [], total: 0, page: 1, pages: 1 });
        
        // Filters
        const donationStatusFilter = ref('');
        const driveStatusFilter = ref('');
        const volunteerStatusFilter = ref('');
        const auditFilters = reactive({user_id: null});
        
        // Chart ref
        const donationsChart = ref(null);
        let chartInstance = null;

        // Computed
        const filteredVolunteers = computed(() => {
            if (!volunteerStatusFilter.value) return volunteers.value.items;
            return volunteers.value.items.filter(v => v.status === volunteerStatusFilter.value);
        });

        // Constants
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
                
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                currentUser.value = data.user;
                isAuthenticated.value = true;
                setActiveTab('dashboard');

            } catch (e) {
                loginError.value = 'Ошибка сети';
            } finally {
                loading.value = false;
            }
        };

        const open2FAModal = async () => {
            // Если 2FA уже включена, показываем окно отключения
            if (currentUser.value.two_factor_enabled) {
                twoFactorStep.value = 'disable';
                twoFactorModal.value = true;
            } else {
                // Если не включена – запускаем процесс настройки
                await setupTwoFactor(); // этот метод должен получать QR-код и секрет
                // setupTwoFactor сам установит twoFactorStep в 'setup' и откроет модалку
            }
        };

        const verifyTwoFactor = async () => {
            loading.value = true;
            try {
                const response = await fetch('/api/auth/2fa/verify', {
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
                isAuthenticated.value = true;
                twoFactorModal.value = false;
                twoFactorForm.token = '';
                twoFactorForm.useBackup = false;
                setActiveTab('dashboard');

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

        const loadSidebar = async () => {
            sidebarLoading.value = true;
            sidebarError.value = '';
            try {
                const response = await apiFetch('/api/admin/sidebar');
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Ошибка загрузки боковой панели');
                }
                sidebarData.value = await response.json();
            } catch (e) {
                sidebarError.value = e.message;
                console.error('Sidebar load failed', e);
            } finally {
                sidebarLoading.value = false;
            }
        };
        
        watch(() => statsData.count_new_donations, () => {
            loadSidebar();
        });

        watch(() => statsData.count_active_drives, () => {
            loadSidebar();
        });

        watch(() => statsData.count_not_verified_news, () => {
            loadSidebar();
        });

        watch(() => statsData.count_new_volunteers, () => {
            loadSidebar();
        });

        const loadDashboard = async () => {
            try {
                const response = await apiFetch('/api/admin/dashboard');
                const data = await response.json();
                dashboardData.value = {
                    donations: { 
                        total: data.donations.total, 
                        total_amount: data.donations.total_amount, 
                        change: data.donations.change, 
                        recent_donations: data.donations.recent_donations },
                    volunteers: { 
                        total: data.volunteers.total },
                    chart: { 
                        labels: data.chart.labels, 
                        datasets: [{ label: data.chart.datasets[0].label, data: data.chart.datasets[0].data}] }
                };

                // Update chart
                if (donationsChart.value) {
                    if (chartInstance) chartInstance.destroy();
                    const ctx = donationsChart.value.getContext('2d');
                    chartInstance = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: dashboardData.value.chart.labels,
                            datasets: [{
                                label: dashboardData.value.chart.datasets[0].label,
                                data: dashboardData.value.chart.datasets[0].data,
                                borderColor: 'rgb(59, 130, 246)',
                                backgroundColor: 'rgb(59, 130, 246)',
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

        const loadStats = async () => {
            statsLoading.value = true;
            statsError.value = '';
            try {
                const response = await apiFetch('/api/admin/stats');
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Ошибка загрузки статистики');
                }
                statsData.value = await response.json();
            } catch (e) {
                statsError.value = e.message;
                console.error('Stats load failed', e);
            } finally {
                statsLoading.value = false;
            }
        };

        const loadDonations = async (page = 1) => {
            try {
                let url = `/api/admin/donations?page=${page}`;
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

        const updateDonationStatus = async (id, status) => {
            try {
                const response = await apiFetch(`/api/admin/donations/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status })
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || 'Ошибка при обновлении статуса');
                }

                loadSidebar()

                showNotification('Статус обновлен');
                
            } catch (e) {
                showNotification('Ошибка1', 'error');
            }
        };

        const loadDrives = async (page = 1) => {
            try {
                let url = `/api/admin/drives?page=${page}`;
                if (driveStatusFilter.value) {
                    url += `&status=${encodeURIComponent(driveStatusFilter.value)}`;
                }
                const response = await apiFetch(url);
                const data = await response.json();
                drives.value = data;
            } catch (e) {
                console.error('Ошибка загрузки сборов:', e);
            }
        };

        const resetDriveForm = () => {
            driveForm.title = '';
            driveForm.description = '';
            driveForm.needs = [];
            driveForm.status = 'активен';
            driveForm.collected = 0;
            driveForm.needed = 0;
            driveError.value = '';
        };

        const openAddDriveModal = () => {
            driveModalMode.value = 'add';
            editingDriveId.value = null;
            resetDriveForm();
            showDriveModal.value = true;
        };

        const editDrive = (drive) => {
            driveModalMode.value = 'edit';
            editingDriveId.value = drive.id;
            driveForm.title = drive.title;
            driveForm.description = drive.description || '';
            driveForm.needs = drive.needs || [];
            driveForm.status = drive.status;
            driveForm.collected = drive.collected;
            driveForm.needed = drive.needed;
            showDriveModal.value = true;
        };

        const saveDrive = async () => {
            driveLoading.value = true;
            driveError.value = '';
            try {
                let url = '/api/admin/drives';
                let method = 'POST';
                if (driveModalMode.value === 'edit') {
                    url = `/api/admin/drives/${editingDriveId.value}`;
                    method = 'PUT';
                }
                const response = await apiFetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(driveForm)
                });
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Ошибка сохранения');
                }
                showNotification(
                    driveModalMode.value === 'add' ? 'Сбор создан' : 'Сбор обновлён',
                    'success'
                );
                showDriveModal.value = false;
                resetDriveForm();
                loadDrives(drives.value.page);
            } catch (e) {
                driveError.value = e.message;
            } finally {
                driveLoading.value = false;
            }
        };

        const confirmDeleteDrive = (driveId) => {
            if (confirm('Вы уверены, что хотите удалить этот сбор?')) {
                deleteDrive(driveId);
            }
        };

        const deleteDrive = async (driveId) => {
            try {
                const response = await apiFetch(`/api/admin/drives/${driveId}`, {
                    method: 'DELETE'
                });
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Ошибка удаления');
                }
                showNotification('Сбор удалён', 'success');
                loadDrives(drives.value.page);
            } catch (e) {
                showNotification(e.message, 'error');
            }
        };

        const prevDrivesPage = () => {
            if (drives.value.page > 1) {
                loadDrives(drives.value.page - 1);
            }
        };

        const nextDrivesPage = () => {
            if (drives.value.page < drives.value.pages) {
                loadDrives(drives.value.page + 1);
            }
        };

        watch(driveStatusFilter, () => {
            loadDrives(1);
        });

        const loadNews = async (page = 1) => {
            try {
                let url = `/api/admin/news?page=${page}`;
                const params = new URLSearchParams();
                if (newsCategoryFilter.value) params.append('category', newsCategoryFilter.value);
                if (newsVerifiedFilter.value) params.append('verified', newsVerifiedFilter.value);
                if (params.toString()) url += '&' + params.toString();

                const response = await apiFetch(url);
                const data = await response.json();
                news.value = data;
            } catch (e) {
                console.error('Ошибка загрузки новостей:', e);
            }
        };

        const openAddNewsModal = () => {
            newsModalMode.value = 'add';
            editingNewsId.value = null;
            resetNewsForm();
            showNewsModal.value = true;
        };

        const editNews = (item) => {
            newsModalMode.value = 'edit';
            editingNewsId.value = item.id;
            newsForm.title = item.title;
            newsForm.slug = item.slug;
            newsForm.excerpt = item.excerpt || '';
            newsForm.content = item.content || '';
            newsForm.category = item.category;
            newsForm.is_verified = item.is_verified;
            newsForm.main_image = item.main_image || '';
            showNewsModal.value = true;
        };

        const resetNewsForm = () => {
            newsForm.title = '';
            newsForm.slug = '';
            newsForm.excerpt = '';
            newsForm.content = '';
            newsForm.category = 'новости';
            newsForm.is_verified = false;
            newsForm.main_image = '';
            newsError.value = '';
        };

        const saveNews = async () => {
            newsLoading.value = true;
            newsError.value = '';
            try {
                let url = '/api/admin/news';
                let method = 'POST';
                if (newsModalMode.value === 'edit') {
                    url = `/api/admin/news/${editingNewsId.value}`;
                    method = 'PUT';
                }
                const response = await apiFetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(newsForm)
                });
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Ошибка сохранения');
                }
                showNotification(
                    newsModalMode.value === 'add' ? 'Новость создана' : 'Новость обновлена',
                    'success'
                );
                showNewsModal.value = false;
                resetNewsForm();
                loadNews(news.value.page);
            } catch (e) {
                newsError.value = e.message;
            } finally {
                newsLoading.value = false;
            }
        };

        const confirmDeleteNews = (id) => {
            if (confirm('Вы уверены, что хотите удалить эту новость?')) {
                deleteNews(id);
            }
        };

        const deleteNews = async (id) => {
            try {
                const response = await apiFetch(`/api/admin/news/${id}`, {
                    method: 'DELETE'
                });
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Ошибка удаления');
                }
                showNotification('Новость удалена', 'success');
                loadNews(news.value.page);
            } catch (e) {
                showNotification(e.message, 'error');
            }
        };

        const prevNewsPage = () => {
            if (news.value.page > 1) {
                loadNews(news.value.page - 1);
            }
        };
        const nextNewsPage = () => {
            if (news.value.page < news.value.pages) {
                loadNews(news.value.page + 1);
            }
        };

        watch([newsCategoryFilter, newsVerifiedFilter], () => {
            loadNews(1);
        });

        const uploadNewsImage = async (file) => {
            const formData = new FormData();
            formData.append('file', file);
            try {
                const response = await apiFetch('/api/admin/upload?subfolder=news', {
                    method: 'POST',
                    body: formData
                });
                if (!response.ok) throw new Error('Ошибка загрузки');
                const data = await response.json();
                newsForm.main_image = data.url;
                showNotification('Изображение загружено', 'success');
            } catch (e) {
                showNotification(e.message, 'error');
            }
        };

        const generateSlug = (text) => {
            if (!text) return '';
            return text
                .split('')
                .map(ch => translitMap[ch] || '')
                .join('')
                .replace(/-+/g, '-')       // убираем повторяющиеся дефисы
                .replace(/^-|-$/g, '')      // убираем дефисы в начале и конце
                .toLowerCase();
        };

        watch(() => newsForm.title, (newTitle, oldTitle) => {
            if (!slugManuallyEdited.value && newTitle) {
                const generated = generateSlug(newTitle);
                if (!newsForm.slug || newsForm.slug === generateSlug(oldTitle)) {
                    newsForm.slug = generated;
                }
            }
        });

        watch(() => newsForm.slug, (newSlug) => {
            if (newSlug && newSlug !== generateSlug(newsForm.title)) {
                slugManuallyEdited.value = true;
            }
        });

        watch(showNewsModal, (val) => {
            if (val && newsModalMode.value === 'add') {
                slugManuallyEdited.value = false;
            }
        });

        watch(() => newsModalMode.value, (mode) => {
            if (mode === 'edit') {
                slugManuallyEdited.value = true;
            }
        });

        const loadSettings = async () => {
            settingsLoading.value = true;
            settingsError.value = '';
            try {
                const response = await apiFetch('/api/admin/settings');
                if (!response.ok) {
                    throw new Error('Ошибка загрузки настроек');
                }
                settingsData.value = await response.json();
            } catch (e) {
                settingsError.value = e.message;
            } finally {
                settingsLoading.value = false;
            }
        };

        const saveSettings = async () => {
            settingsSaving.value = true;
            settingsError.value = '';
            try {
                const response = await apiFetch('/api/admin/settings', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settingsData.value)
                });
                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Ошибка сохранения');
                }
                showNotification('Настройки сохранены', 'success');
            } catch (e) {
                settingsError.value = e.message;
            } finally {
                settingsSaving.value = false;
            }
        };

        const resetSettings = () => {
            if (confirm('Сбросить все изменения?')) {
                loadSettings();
            }
        };

        const loadVolunteers = async (page = 1) => {
            try {
                let url = `/api/admin/volunteers?page=${page}`;
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
                loadVolunteers(volunteers.value.page - 1);
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

        const updateVolunteerStatus = async (id, status) => {
            try {
                const response = await apiFetch(`/api/admin/volunteers/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status })
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || 'Ошибка при обновлении статуса');
                }

                loadSidebar()

                showNotification('Статус обновлен');

            } catch (e) {
                showNotification('Ошибка', 'error');
            }
        };

        const loadAdminUsers = async (page = 1) => {
            try {
                const url = `/api/admin/users?page=${page}`;
                const response = await apiFetch(url);
                const data = await response.json();
                adminUsers.value = data;
            } catch (e) {
                console.error('Ошибка загрузки пользователей:', e);
            }
        };

        const prevUsersPage = () => {
            if (adminUsers.value.page > 1) {
                loadAdminUsers(adminUsers.value.page - 1);
            }
        };

        const nextUsersPage = () => {
            if (adminUsers.value.page < adminUsers.value.pages) {
                loadAdminUsers(adminUsers.value.page + 1);
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
                    loadAdminUsers(adminUsers.value.page);
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

                if (activeTab.value === 'users') {
                    loadAdminUsers(adminUsers.value.page);
                }
                
                closeEditUserModal()

                if (activeTab.value === 'users') {
                    if (adminUsers.items.length === 0 && adminUsers.value.page > 1) {
                        loadAdminUsers(adminUsers.value.page - 1);
                    } else {
                        loadAdminUsers(adminUsers.value.page);
                    }
                }

            } catch (e) {
                userError.value = 'Ошибка сети';
            } finally {
                userLoading.value = false;
            }
        };

        const toggleUserStatus = async (user) => {
            const action = user.is_active ? 'деактивировать' : 'активировать';

            try {
                const response = await apiFetch(`/api/admin/users/${user.id}/toggle`, {
                    method: 'POST'
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || `Не удалось ${action} пользователя ${user.id}`);
                }

                const result = await response.json();
                showNotification(result.message || `Удалось успешно ${action} пользователя ${user.id}`, 'success');

                if (activeTab.value === 'users') {
                    loadAdminUsers(adminUsers.value.page);
                }

            } catch (e) {
                showNotification(e.message, 'error');
            }
        };

        const loadAudit = async (page = 1) => {
            try {
                let url = `/api/admin/audit?page=${page}`;
                if (auditFilters.user_id) {
                    url += `&user_id=${auditFilters.user_id}`;
                }
                const response = await apiFetch(url);
                const data = await response.json();
                auditLogs.value = data;
            } catch (e) {
                console.error('Ошибка загрузки логов:', e);
            }
        };

        const prevAuditPage = () => {
            if (auditLogs.value.page > 1) {
                loadAudit(auditLogs.value.page - 1);
            }
        };

        const nextAuditPage = () => {
            if (auditLogs.value.page < auditLogs.value.pages) {
                loadAudit(auditLogs.value.page + 1);
            }
        };

        watch(() => auditFilters.user_id, () => {
            loadAudit(1);
        });

        const setActiveTab = (tab) => {
            activeTab.value = tab;
            if (tab) loadSidebar();
            if (tab === 'dashboard') loadDashboard();
            if (tab === 'stats') loadStats();
            if (tab === 'donations') loadDonations(1);
            if (tab === 'drives') loadDrives(1);
            if (tab === 'news') loadNews(1);
            if (tab === 'volunteers') loadVolunteers();
            if (tab === 'users') loadAdminUsers(1);
            if (tab === 'audit') loadAudit(1);
            if (tab === 'settings') loadSettings();
        };

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
                stats: 'Подробная статистика',
                donations: 'Управление входящими пожертвованиями',
                drives: 'Управление сборами',
                news: 'Управление новостной лентой',
                volunteers: 'Управление заявками волонтёров',
                users: 'Управление администраторами и модераторами',
                audit: 'Аудит последних действий администраторов',
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

        // const formatDate = (iso) => {
        //     if (!iso) return '';
        //     const d = new Date(iso);
        //     return d.toLocaleString('ru-RU');
        // };

        function formatDate(isoString) {
            if (!isoString) return '';
            const date = new Date(isoString);
            if (isNaN(date.getTime())) return isoString;

            const options = {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                timeZone: 'Europe/Moscow'
            };
            return new Intl.DateTimeFormat('ru-RU', options).format(date);
        }

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
                    headers: { 'Content-Type': 'application/json' },
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
                    headers: { 'Content-Type': 'application/json' },
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
                    currentUser.value = user
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
                        loadSidebar();
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
            
            sidebarData,

            dashboardData,

            statsData,
            statsLoading,
            statsError,

            news,
            newsCategoryFilter,
            newsVerifiedFilter,
            showNewsModal,
            newsModalMode,
            editingNewsId,
            newsForm,
            newsLoading,
            newsError,

            translitMap,
            slugManuallyEdited,

            settingsData,
            settingsLoading,
            settingsSaving,
            settingsError,

            showUserModal,
            userLoading,
            userError,
            userForm,

            editUserModal,
            editingUserId,

            showDriveModal,
            driveModalMode,
            editingDriveId,
            driveForm,
            driveLoading,
            driveError,
            needsText,

            activeTab,
            notification,

            donations,
            recentDonations,
            drives,
            news,
            volunteers,
            adminUsers,
            auditLogs,

            donationStatusFilter,
            driveStatusFilter,
            volunteerStatusFilter,
            auditFilters,

            donationsChart,

            // Computed
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

            resetDriveForm,
            openAddDriveModal,
            editDrive,
            saveDrive,
            confirmDeleteDrive,
            deleteDrive,
            prevDrivesPage,
            nextDrivesPage,

            openAddNewsModal,
            editNews,
            resetNewsForm,
            saveNews,
            confirmDeleteNews,
            deleteNews,
            prevNewsPage,
            nextNewsPage,

            uploadNewsImage,

            generateSlug,

            saveSettings,
            resetSettings,

            prevVolunteersPage,
            nextVolunteersPage,
            updateDonationStatus,
            updateVolunteerStatus,
            prevUsersPage,
            nextUsersPage,
            createUser,
            resetUserForm,
            editUser,
            closeEditUserModal,
            saveUser,
            confirmDeleteUser,
            deleteUser,
            toggleUserStatus,
            prevAuditPage,
            nextAuditPage,
            setActiveTab,
            getTabTitle,
            getTabDescription,
            formatCurrency,
            formatPercent,
            formatDate,
            showNotification,
            hasPermission,

            // 2FA
            open2FAModal,
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