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
        const drivesFilter = ref('');

        // News
        const news = ref({ items: [] });
        const featuredArticle = ref(null);
        const newsFilter = ref('');
        
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

        const fetchDrives = async () => {
            try {
                let url = `/api/public/drives`
                if (drivesFilter.value) {
                    url += `?status=${encodeURIComponent(drivesFilter.value)}`;
                }
                const response = await fetch(url);
                const data = await response.json();
                drives.value = data;
            } catch (e) {
                console.error('Failed to fetch drives', e);
            }
        };

        const fetchNews = async () => {
            try {
                let url = `/api/public/news`
                if (newsFilter.value) {
                    url += `?status=${encodeURIComponent(newsFilter.value)}`;
                }
                const response = await fetch(url);
                const data = await response.json();
                news.value = data;
                if (data.length > 0) {
                    featuredArticle.value = data[0];
                }

            } catch (e) {
                console.error('Failed to fetch news', e);
            }
        };

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
                    showNotification(err.error || 'Ошибка при отправке', 'error');
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
                        is_anonymous: donationForm.is_anonymous
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
                    showNotification(err.error || 'Ошибка при отправке', 'error');
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

        const setNewsFilter = (filter) => {
            newsFilter.value = filter;
        };

        const setDrivesFilter = (filter) => {
            drivesFilter.value = filter;
        };

        const getCategoryName = (cat) => {
            const map = {
                'новости': 'Новости',
                'отчёт': 'Отчёт',
                'история': 'История'
            };
            return map[cat] || cat;
        };

        const getUrgencyText = (urgency) => {
            const map = {
                'высокая': 'Срочно!',
                'средняя': 'Средняя',
                'низкая': 'Низкая'
            };
            return map[urgency] || urgency;
        };

        const getUrgencyIcon = (urgency) => {
            const map = {
                'высокая': 'fas fa-exclamation-triangle',
                'средняя': 'fas fa-clock',
                'низкая': 'fas fa-check'
            };
            return map[urgency] || 'fas fa-info';
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
            fetchStats();
            fetchDrives();
            fetchNews();
        });

        return {
            stats,
            drives,
            drivesFilter,
            news,
            featuredArticle,
            newsFilter,
            filteredNews,
            filteredDrives,
            donationForm,
            donationLoading,
            volunteerForm,
            volunteerLoading,
            showDonationModal,
            notification,
            setDrivesFilter,
            scrollTo,
            submitDonation,
            submitVolunteer,
            showDonationForDrive,
            viewArticle,
            setNewsFilter,
            getCategoryName,
            getUrgencyText,
            getUrgencyIcon,
            formatCurrency
        };
    }
});

app.mount('#app');