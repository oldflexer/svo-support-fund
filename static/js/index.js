const { createApp, ref, reactive, onMounted, computed } = Vue;

const app = createApp({
    delimiters: ['${', '}'],
    setup() {
        // Stats
        const stats = ref({
            sum_donation: 0,
            count_volunteers: 0
        });

        // Drives
        const drives = ref({ items: [] });
        const drivesFilter = ref('активен');
        const drivesPage = ref(1);
        const drivesPerPage = ref(3);
        const drivesTotalPages = ref(1);

        const drivesList = ref([]);
        const selectedDriveId = ref(null);
        
        // News
        const news = ref({ items: [] });
        const featuredArticle = ref(null);
        const newsFilter = ref('');
        const newsPage = ref(1);
        const newsPerPage = ref(4);
        const newsTotalPages = ref(1);
        
        // Volunteer form
        const volunteerForm = reactive({
            name: '',
            email: '',
            phone: '',
            city: '',
            skills: '',
            can_deliver: false
        });
        const volunteerLoading = ref(false);

        // Donation form
        const donationForm = reactive({
            name: '',
            amount: 1000,
            message: '',
            is_anonymous: false
        });
        const donationLoading = ref(false);
        
        // UI
        const showDonationModal = ref(false);

        const notification = reactive({
            show: false,
            type: 'success',
            icon: '',
            message: ''
        });

        // Computed
        const filteredNews = computed(() => {
            if (!newsFilter.value) return news.value.items;
            return news.value.items.filter(item => item.category === newsFilter.value);
        });

        const filteredDrives = computed(() => {
            if (!drivesFilter.value) return drives.value.items;
            return drives.value.items.filter(item => item.status === drivesFilter.value);
        });

        // Methods
        const fetchStats = async () => {
            try {
                const response = await fetch('/api/public/stats');
                const data = await response.json();
                stats.value = data;
            } catch (e) {
                console.error('Failed to fetch stats', e);
            }
        };

        const fetchDrives = async (page = drivesPage.value) => {
            try {
                let url = `/api/public/drives?page=${page}&per_page=${drivesPerPage.value}`;
                if (drivesFilter.value) {
                    url += `&status=${encodeURIComponent(drivesFilter.value)}`;
                }
                const response = await fetch(url);
                const data = await response.json();
                drives.value = data;
                drivesTotalPages.value = data.pages;
                drivesPage.value = data.page;
            } catch (e) {
                console.error('Failed to fetch drives', e);
            }
        };

        const prevDrivesPage = () => {
            if (drivesPage.value > 1) {
                fetchDrives(drivesPage.value - 1);
            }
        };

        const nextDrivesPage = () => {
            if (drivesPage.value < drivesTotalPages.value) {
                fetchDrives(drivesPage.value + 1);
            }
        };

        const setDrivesFilter = (filter) => {
            drivesFilter.value = filter;
            drivesPage.value = 1;
            fetchDrives(1);
        };

        const fetchDrivesForSelect = async () => {
            try {
                const response = await fetch('/api/public/drives?status=активен');
                const data = await response.json();
                drivesList.value = data.items || [];
            } catch (e) {
                console.error('Failed to fetch drives for select', e);
            }
        };

        const fetchNews = async (page = newsPage.value) => {
            try {
                let url = `/api/public/news?page=${page}&per_page=${newsPerPage.value}`;
                if (newsFilter.value) {
                    url += `&category=${encodeURIComponent(newsFilter.value)}`;
                }
                const response = await fetch(url);
                const data = await response.json();
                news.value = data;
                newsTotalPages.value = data.pages;
                newsPage.value = data.page;
                if (data.items && data.items.length > 0) {
                    featuredArticle.value = data.items[0];
                } else {
                    featuredArticle.value = null;
                }
            } catch (e) {
                console.error('Failed to fetch news', e);
            }
        };

        const prevNewsPage = () => {
            if (newsPage.value > 1) {
                fetchNews(newsPage.value - 1);
            }
        };

        const nextNewsPage = () => {
            if (newsPage.value < newsTotalPages.value) {
                fetchNews(newsPage.value + 1);
            }
        };

        const setNewsFilter = (filter) => {
            newsFilter.value = filter;
            newsPage.value = 1;
            fetchNews(1);
        };

        const categoryPlaceholder = (category) => {
            const placeholders = {
                'новости': '../static/img/news.png',
                'отчёт': '../static/img/reports.png',
                'история': '../static/img/tales.png'
            };
            return placeholders[category] || '../static/img/news.png'; // запасной вариант
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

        const scrollTo = (id) => {
            const element = document.getElementById(id);
            if (element) {
                element.scrollIntoView({ behavior: 'smooth' });
            }
        };

        const submitVolunteer = async () => {
            volunteerLoading.value = true;
            try {
                const response = await fetch('/api/public/volunteers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: volunteerForm.name,
                        email: volunteerForm.email,
                        phone: volunteerForm.phone,
                        city: volunteerForm.city,
                        skills: volunteerForm.skills,
                        can_deliver: volunteerForm.can_deliver
                    })
                });
                if (response.ok) {
                    fetchStats();
                    showNotification('Спасибо за желание помочь! Мы свяжемся с вами.', 'success');
                    volunteerForm.name = '';
                    volunteerForm.email = '';
                    volunteerForm.phone = '';
                    volunteerForm.city = '';
                    volunteerForm.skills = '';
                    volunteerForm.can_deliver = false;
                } else {
                    const err = await response.json();
                    showNotification(err.errors || 'Ошибка при отправке', 'error');
                }
            } catch (e) {
                showNotification('Ошибка сети', 'error');
            } finally {
                volunteerLoading.value = false;
            }
        };

        const submitDonation = async () => {
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
                    fetchStats();
                    showNotification('Спасибо за ваше пожертвование!', 'success');
                    donationForm.name = '';
                    donationForm.amount = 1000;
                    donationForm.message = '';
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
        };

        const showDonationForDrive = (driveId) => {
            // Could pre-fill drive info
            showDonationModal.value = true;
        };

        const viewArticle = (slug) => {
            window.location.href = `/news/${slug}`; // or open modal
        };

        const getCategoryName = (cat) => {
            const map = {
                'новости': 'Новости',
                'отчёт': 'Отчёт',
                'история': 'История'
            };
            return map[cat] || cat;
        };

        const formatCurrency = (value) => {
            return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', minimumFractionDigits: 0 }).format(value);
        };

        const showNotification = (message, type = 'success') => {
            notification.message = message;
            notification.type = type;
            notification.icon = type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle';
            notification.show = true;
            setTimeout(() => {
                notification.show = false;
            }, 5000);
        };

        // Lifecycle
        onMounted(() => {
            fetchDrivesForSelect();
            fetchStats();
            fetchDrives(1);
            fetchNews(1);
        });

        return {
            stats,

            drives,
            drivesFilter,
            filteredDrives,
            drivesPage,
            drivesPerPage,
            drivesTotalPages,

            drivesList,
            selectedDriveId,

            news,
            featuredArticle,
            newsFilter,
            filteredNews,
            newsPage,
            newsPerPage,
            newsTotalPages,

            volunteerForm,
            volunteerLoading,
            
            donationForm,
            donationLoading,
            showDonationModal,
            
            notification,
            
            prevDrivesPage,
            nextDrivesPage,
            setDrivesFilter,

            prevNewsPage,
            nextNewsPage,
            setNewsFilter,
            getCategoryName,
            categoryPlaceholder,
            viewArticle,

            submitVolunteer,

            submitDonation,
            showDonationForDrive,
            
            scrollTo,
            
            formatCurrency,
            formatDate
        };
    }
});

app.mount('#app');