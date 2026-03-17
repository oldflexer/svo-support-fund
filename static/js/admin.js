const { createApp, ref, reactive, onMounted, onUnmounted, computed, watch } = Vue;

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
        const driveModalMode = ref('add');
        const editingDriveId = ref(null);
        const driveForm = reactive({
            title: '',
            description: '',
            needs: [],
            status: 'активен',
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
        const showNewsModal = ref(false);
        const newsModalMode = ref('add');
        const editingNewsId = ref(null);
        const newsForm = reactive({
            title: '',
            slug: '',
            excerpt: '',
            content: '',
            category: 'новости',
            is_verified: false,
            main_image: '',
            images: []
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

        const newsCategoryFilter = ref('');
        const newsVerifiedFilter = ref('');
        const additionalImagesLoading = ref(false);

        // New user modal
        const showUserModal = ref(false);
        const userModalMode = ref('add');
        const editingUserId = ref(null);
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
        
        // UI state
        const activeTab = ref('dashboard');
        const notification = reactive({ show: false, type: 'success', icon: '', message: '' });
        
        // Data tables
        const recentDonations = ref([]);
        
        // Filters
        const donationStatusFilter = ref('');
        const driveStatusFilter = ref('');
        const volunteerStatusFilter = ref('');
        const auditFilters = reactive({ user_id: null });
        
        // Chart ref
        const donationsChart = ref(null);
        let chartInstance = null;

        // Computed
        const filteredVolunteers = computed(() => {
            if (!volunteerStatusFilter.value) return volunteers.items.value;
            return volunteers.items.value.filter(v => v.status === volunteerStatusFilter.value);
        });

        const auditUserId = computed({
            get: () => auditFilters.user_id,
            set: (val) => { auditFilters.user_id = val; }
        });

        // Constants
        const roleLabels = {
            admin: 'Администратор',
            moderator: 'Модератор'
        };

        const lastNotificationCheck = ref(new Date().toISOString());
        const notificationPollInterval = ref(null);

        // Methods
        const apiFetch = async (url, options = {}) => {
            let accessToken = localStorage.getItem('access_token');
            if (accessToken) {
                options.headers = {
                    ...options.headers,
                    'Authorization': `Bearer ${accessToken}`
                };
            }

            let response = await fetch(url, options);

            if (response.status !== 401) {
                return response;
            }

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

                options.headers['Authorization'] = `Bearer ${data.access_token}`;
                return await fetch(url, options);
            } catch (e) {
                logout();
                throw e;
            }
        };

        // Create paginated loaders
        const donations = createPaginatedLoader('/api/admin/donations', { status: donationStatusFilter }, apiFetch);
        const drives = createPaginatedLoader('/api/admin/drives', { status: driveStatusFilter }, apiFetch, {perPage: 5});
        const volunteers = createPaginatedLoader('/api/admin/volunteers', { status: volunteerStatusFilter }, apiFetch);
        const news = createPaginatedLoader('/api/admin/news', { category: newsCategoryFilter, verified: newsVerifiedFilter }, apiFetch, {perPage: 5});
        const adminUsers = createPaginatedLoader('/api/admin/users', {}, apiFetch);
        const auditLogs = createPaginatedLoader('/api/admin/audit', { user_id: auditUserId }, apiFetch);

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
            if (currentUser.value.two_factor_enabled) {
                twoFactorStep.value = 'disable';
                twoFactorModal.value = true;
            } else {
                await setupTwoFactor();
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
        
        watch(() => statsData.value?.count_new_donations, () => {
            loadSidebar();
        });

        watch(() => statsData.value?.count_active_drives, () => {
            loadSidebar();
        });

        watch(() => statsData.value?.count_not_verified_news, () => {
            loadSidebar();
        });

        watch(() => statsData.value?.count_new_volunteers, () => {
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

                loadSidebar();
                showNotification('Статус обновлен');
                
            } catch (e) {
                showNotification(e.message, 'error');
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
                drives.load(drives.page.value);
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
                drives.load(drives.page.value);
            } catch (e) {
                showNotification(e.message, 'error');
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
            newsForm.images = (item.images || []).map(img => ({ url: img.url, id: img.id }));
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
            newsForm.images = [];
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
                const payload = {
                    title: newsForm.title,
                    slug: newsForm.slug,
                    excerpt: newsForm.excerpt,
                    content: newsForm.content,
                    category: newsForm.category,
                    main_image: newsForm.main_image,
                    is_verified: newsForm.is_verified,
                    additional_images: newsForm.images.map(img => img.url)
                };
                const response = await apiFetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
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
                news.load(news.page.value);
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
                news.load(news.page.value);
            } catch (e) {
                showNotification(e.message, 'error');
            }
        };

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

        const uploadAdditionalImages = async (event) => {
            const files = Array.from(event.target.files);
            if (files.length === 0) return;

            additionalImagesLoading.value = true;
            let successCount = 0;
            let errorCount = 0;

            try {
                for (const file of files) {
                    const formData = new FormData();
                    formData.append('file', file);
                    try {
                        const response = await apiFetch('/api/admin/upload?subfolder=news', {
                            method: 'POST',
                            body: formData
                        });
                        if (response.ok) {
                            const data = await response.json();
                            newsForm.images.push({ 
                                url: data.url, 
                                tempId: Date.now() + Math.random() + successCount
                            });
                            successCount++;
                        } else {
                            const error = await response.json();
                            showNotification(`Ошибка загрузки файла ${file.name}: ${error.error || 'Неизвестная ошибка'}`, 'error');
                            errorCount++;
                        }
                    } catch (e) {
                        showNotification(`Ошибка сети при загрузке файла ${file.name}`, 'error');
                        errorCount++;
                    }
                }
                if (successCount > 0) {
                    showNotification(`Загружено изображений: ${successCount}${errorCount > 0 ? `, ошибок: ${errorCount}` : ''}`, 'success');
                }
            } finally {
                additionalImagesLoading.value = false;
                event.target.value = '';
            }
        };

        const removeImage = (index) => {
            newsForm.images.splice(index, 1);
        };

        const generateSlug = (text) => {
            if (!text) return '';
            return text
                .split('')
                .map(ch => translitMap[ch] || '')
                .join('')
                .replace(/-+/g, '-')
                .replace(/^-|-$/g, '')
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

                loadSidebar();
                showNotification('Статус обновлен');

            } catch (e) {
                showNotification(e.message, 'error');
            }
        };

        const openAddUserModal = () => {
            userModalMode.value = 'add';
            editingUserId.value = null;
            resetUserForm();
            showUserModal.value = true;
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
        };

        const saveUser = async () => {
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
                showNotification(
                    userModalMode.value === 'add' ? 'Пользователь создан' : 'Пользователь обновлен',
                    'success'
                );
                showUserModal.value = false;
                resetUserForm();
                if (activeTab.value === 'users') {
                    adminUsers.load(adminUsers.page.value);
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
                    if (adminUsers.items.value.length === 0 && adminUsers.page.value > 1) {
                        adminUsers.load(adminUsers.page.value - 1);
                    } else {
                        adminUsers.load(adminUsers.page.value);
                    }
                }
                showUserModal.value = false

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
                    throw new Error(error.error || `Не удалось ${action} пользователя`);
                }

                const result = await response.json();
                showNotification(result.message || `Пользователь успешно ${action}`, 'success');

                if (activeTab.value === 'users') {
                    adminUsers.load(adminUsers.page.value);
                }

            } catch (e) {
                showNotification(e.message, 'error');
            }
        };

        const setActiveTab = (tab) => {
            activeTab.value = tab;
            if (tab) loadSidebar();
            if (tab === 'dashboard') loadDashboard();
            if (tab === 'stats') loadStats();
            if (tab === 'donations') donations.load(1);
            if (tab === 'drives') drives.load(1);
            if (tab === 'news') news.load(1);
            if (tab === 'volunteers') volunteers.load(1);
            if (tab === 'users') adminUsers.load(1);
            if (tab === 'audit') {
                auditLogs.load(1);
                adminUsers.load(1);
            }
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
            notification.icon =
                type === 'success' ? 'fas fa-check-circle' : 
                type === 'error' ? 'fas fa-exclamation-circle' : 
                'fas fa-info-circle';
            notification.show = true;
            setTimeout(() => notification.show = false, 5000);
        };

        const formatCurrency = (value) => {
            return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', minimumFractionDigits: 0 }).format(value);
        };

        const formatPercent = (value) => {
            return new Intl.NumberFormat('ru-RU', { style: 'percent', minimumFractionDigits: 0 }).format(value);
        };

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

        const hasPermission = (roles) => {
            return roles.includes(currentUser.value.role);
        };

        const pollNotifications = async () => {
            try {
                const response = await apiFetch(`/api/admin/notifications?last_check=${encodeURIComponent(lastNotificationCheck.value)}`);
                if (!response.ok) return;
                const data = await response.json();
                lastNotificationCheck.value = data.server_time;

                if (data.new_donations > 0 || data.new_volunteers > 0) {
                    let parts = [];
                    if (data.new_donations > 0) parts.push(`${data.new_donations} новых пожертвований`);
                    if (data.new_volunteers > 0) parts.push(`${data.new_volunteers} новых заявок волонтёров`);
                    showNotification(parts.join(' и '), 'info');
                    loadSidebar(); // обновляем счётчики
                }
            } catch (e) {
                console.error('Polling error', e);
            }
        };

        onMounted(() => {
            const token = localStorage.getItem('access_token');
            if (token) {
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
                notificationPollInterval.value = setInterval(pollNotifications, 30000);
                pollNotifications();
            }
        });

        onUnmounted(() => {
            if (notificationPollInterval.value) {
                clearInterval(notificationPollInterval.value);
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

            showNewsModal,
            newsModalMode,
            editingNewsId,
            newsForm,
            newsLoading,
            newsError,

            slugManuallyEdited,

            settingsData,
            settingsLoading,
            settingsSaving,
            settingsError,

            showUserModal,
            userModalMode,
            editingUserId,
            userLoading,
            userError,
            userForm,

            showDriveModal,
            driveModalMode,
            editingDriveId,
            driveForm,
            driveLoading,
            driveError,
            needsText,

            activeTab,
            notification,

            // Data tables
            donations,
            recentDonations,
            drives,
            news,
            volunteers,
            adminUsers,
            auditLogs,

            // Filters
            donationStatusFilter,
            driveStatusFilter,
            volunteerStatusFilter,
            newsCategoryFilter,
            newsVerifiedFilter,
            additionalImagesLoading,
            auditFilters,

            donationsChart,

            // Computed
            filteredVolunteers,
            
            // Constants
            roleLabels,

            lastNotificationCheck,
            notificationPollInterval,

            // Methods
            apiFetch,

            login,
            logout,
            refreshToken,
            verifyTwoFactor,

            updateDonationStatus,

            resetDriveForm,
            openAddDriveModal,
            editDrive,
            saveDrive,
            confirmDeleteDrive,
            deleteDrive,

            openAddNewsModal,
            editNews,
            resetNewsForm,
            saveNews,
            confirmDeleteNews,
            deleteNews,

            uploadNewsImage,
            uploadAdditionalImages,
            removeImage,
            generateSlug,

            saveSettings,
            resetSettings,

            updateVolunteerStatus,

            resetUserForm,
            editUser,
            saveUser,
            confirmDeleteUser,
            deleteUser,
            toggleUserStatus,
            openAddUserModal,

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