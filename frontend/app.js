const { createApp, ref, computed, onMounted } = Vue;

createApp({
    setup() {
        // Основные состояния
        const assistanceTypes = ref([]);
        const stats = ref({});

        const showDonationModal = ref(false);

        const currentDrives = ref([]);
        const driveFilter = ref(null);

        // Добавляем состояния для новостей
        const news = ref({
            articles: [],
            total: 0,
            pages: 1,
            currentPage: 1
        });
        const featuredArticle = ref(null);
        const newsFilter = ref(null);
        
        // Формы
        const donationForm = ref({
            name: '',
            amount: 1000,
            assistance_type_id: null,
            message: '',
            is_anonymous: false
        });
        
        const volunteerForm = ref({
            name: '',
            email: '',
            phone: '',
            city: '',
            skills: '',
            can_deliver: false
        });
        
        // Состояния загрузки
        const donationLoading = ref(false);
        const volunteerLoading = ref(false);
        
        // Уведомления
        const notification = ref({
            show: false,
            message: '',
            type: 'success',
            icon: 'fas fa-check-circle'
        });
        
        // API базовый URL
        const API_URL = 'http://localhost:5000';
        
        // Методы
        const fetchData = async () => {
            try {                
                // Загружаем типы помощи
                const typesResponse = await fetch(`${API_URL}/api/assistance/types`);
                assistanceTypes.value = await typesResponse.json();
                
                // Загружаем статистику
                const statsResponse = await fetch(`${API_URL}/api/stats`);
                stats.value = await statsResponse.json();

            } catch (error) {
                showNotification('Ошибка загрузки данных', 'error');
                console.error('Ошибка:', error);
            }
        };
        
        const scrollTo = (elementId) => {
            const element = document.getElementById(elementId);
            if (element) {
                element.scrollIntoView({ behavior: 'smooth' });
            }
        };
        
        const submitDonation = async () => {
            if (!donationForm.value.amount || donationForm.value.amount < 100) {
                showNotification('Минимальная сумма пожертвования - 100 рублей', 'error');
                return;
            }
            
            donationLoading.value = true;
            
            try {
                const response = await fetch(`${API_URL}/api/donate`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(donationForm.value)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showNotification(data.message, 'success');
                    donationForm.value = {
                        name: '',
                        amount: 1000,
                        assistance_type_id: null,
                        message: '',
                        is_anonymous: false
                    };
                    showDonationModal.value = false;
                    
                    // Обновляем статистику
                    fetchData();
                } else {
                    showNotification(data.error || 'Ошибка при отправке пожертвования', 'error');
                }
            } catch (error) {
                showNotification('Ошибка сети. Попробуйте позже.', 'error');
                console.error('Ошибка:', error);
            } finally {
                donationLoading.value = false;
            }
        };
        
        const submitVolunteer = async () => {
            volunteerLoading.value = true;
            
            try {
                const response = await fetch(`${API_URL}/api/volunteer/register`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(volunteerForm.value)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    showNotification(data.message, 'success');
                    volunteerForm.value = {
                        name: '',
                        email: '',
                        phone: '',
                        city: '',
                        skills: '',
                        can_deliver: false
                    };
                } else {
                    showNotification(data.error || 'Ошибка при регистрации', 'error');
                }
            } catch (error) {
                showNotification('Ошибка сети. Попробуйте позже.', 'error');
                console.error('Ошибка:', error);
            } finally {
                volunteerLoading.value = false;
            }
        };
        
        const showNotification = (message, type = 'success') => {
            notification.value = {
                show: true,
                message,
                type,
                icon: type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle'
            };
            
            // Автоматическое скрытие через 5 секунд
            setTimeout(() => {
                notification.value.show = false;
            }, 5000);
        };
        
        const formatCurrency = (amount) => {
            if (!amount) return '0 ₽';
            return new Intl.NumberFormat('ru-RU').format(amount) + ' ₽';
        };

        const fetchCurrentDrives = async () => {
            try {
                const response = await fetch(`${API_URL}/api/unit-requests/public`);
                currentDrives.value = await response.json();
            } catch (error) {
                console.error('Error fetching current drives:', error);
            }
        };

        const setDriveFilter = (filter) => {
            driveFilter.value = filter;
        };

        const filteredDrives = computed(() => {
            if (!driveFilter.value) return currentDrives.value;
            return currentDrives.value.filter(drive => drive.urgency === driveFilter.value);
        });

        const getUrgencyIcon = (urgency) => {
            const icons = {
                'критично': 'fas fa-exclamation-triangle',
                'срочно': 'fas fa-exclamation-circle',
                'обычно': 'fas fa-info-circle'
            };
            return icons[urgency] || 'fas fa-info-circle';
        };

        const getUrgencyText = (urgency) => {
            const texts = {
                'критично': 'Критично',
                'срочно': 'Срочно',
                'обычно': 'Обычно'
            };
            return texts[urgency] || 'Обычно';
        };

        const showDonationForDrive = (driveId) => {
            donationForm.value.unit_request_id = driveId;
            showDonationModal.value = true;
        };

        const viewDriveDetails = (driveId) => {
            // Здесь будет реализация просмотра деталей сбора
            showNotification('Функция просмотра деталей сбора будет реализована в следующей версии', 'info');
        };

        // Добавляем методы для новостей
        const fetchNews = async (page = 1) => {
            try {
                let url = `${API_URL}/api/news?page=${page}&limit=6`;
                if (newsFilter.value) {
                    url += `&category=${newsFilter.value}`;
                }
                
                const response = await fetch(url);
                const data = await response.json();
                
                if (page === 1) {
                    news.value = data;
                    // Находим featured статью
                    featuredArticle.value = data.articles.find(article => article.is_featured) || data.articles[0];
                    // Убираем featured из основного списка
                    if (featuredArticle.value) {
                        news.value.articles = data.articles.filter(article => article.id !== featuredArticle.value.id);
                    }
                } else {
                    news.value.articles = [...news.value.articles, ...data.articles];
                    news.value.total = data.total;
                    news.value.pages = data.pages;
                    news.value.currentPage = page;
                }
            } catch (error) {
                console.error('Error fetching news:', error);
            }
        };

        const loadMoreNews = () => {
            if (news.value.currentPage < news.value.pages) {
                fetchNews(news.value.currentPage + 1);
            }
        };

        const setNewsFilter = (category) => {
            newsFilter.value = category;
            fetchNews(1); // Загружаем первую страницу с новым фильтром
        };

        const filteredNews = computed(() => {
            return news.value.articles;
        });

        const getCategoryName = (category) => {
            const names = {
                'новости': 'Новости фонда',
                'сводка': 'Фронтовые сводки',
                'отчёт': 'Отчёты о помощи',
                'история': 'Истории бойцов'
            };
            return names[category] || category;
        };

        const viewArticle = (slug) => {
            // Здесь будет реализация просмотра статьи
            // Можно открыть в модальном окне или на отдельной странице
            window.open(`${API_URL}/api/news/${slug}`, '_blank');
            // Или показать уведомление
            showNotification('Функция просмотра статьи будет реализована в следующей версии', 'info');
        };
        
        // Инициализация при загрузке
        onMounted(() => {
            fetchData();
            fetchCurrentDrives();
            fetchNews();
            
            // Плавная прокрутка для якорных ссылок
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {
                anchor.addEventListener('click', function (e) {
                    e.preventDefault();
                    const targetId = this.getAttribute('href');
                    if (targetId === '#') return;
                    
                    const targetElement = document.querySelector(targetId);
                    if (targetElement) {
                        targetElement.scrollIntoView({
                            behavior: 'smooth'
                        });
                    }
                });
            });
        });
        
        return {
            // Состояния
            assistanceTypes,
            stats,
            showDonationModal,
            donationForm,
            volunteerForm,
            donationLoading,
            volunteerLoading,
            notification,
            
            // Computed
            filteredDrives,
            filteredNews,
            
            // Методы
            scrollTo,
            submitDonation,
            submitVolunteer,
            showNotification,
            formatCurrency,
            setDriveFilter,
            getUrgencyIcon,
            getUrgencyText,
            showDonationForDrive,
            viewDriveDetails,
            loadMoreNews,
            setNewsFilter,
            getCategoryName,
            viewArticle
        };
    }
}).mount('#app');