const { createApp, ref, computed, onMounted } = Vue;

createApp({
    setup() {
        // Основные состояния
        const fighters = ref([]);
        const assistanceTypes = ref([]);
        const urgentNeeds = ref([]);
        const stats = ref({});
        const activeFilter = ref(null);
        const showDonationModal = ref(false);
        
        // Формы
        const donationForm = ref({
            name: '',
            amount: 1000,
            fighter_id: null,
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
        
        // Отфильтрованные бойцы
        const filteredFighters = computed(() => {
            if (!activeFilter.value) return fighters.value;
            
            if (typeof activeFilter.value === 'string') {
                return fighters.value.filter(f => f.status === activeFilter.value);
            } else {
                return fighters.value.filter(f => f.priority === activeFilter.value);
            }
        });
        
        // Методы
        const fetchData = async () => {
            try {
                // Загружаем бойцов
                const fightersResponse = await fetch(`${API_URL}/api/fighters`);
                fighters.value = await fightersResponse.json();
                
                // Загружаем типы помощи
                const typesResponse = await fetch(`${API_URL}/api/assistance/types`);
                assistanceTypes.value = await typesResponse.json();
                
                // Загружаем срочные потребности
                const needsResponse = await fetch(`${API_URL}/api/needs/urgent`);
                urgentNeeds.value = await needsResponse.json();
                
                // Загружаем статистику
                const statsResponse = await fetch(`${API_URL}/api/stats`);
                stats.value = await statsResponse.json();
            } catch (error) {
                showNotification('Ошибка загрузки данных', 'error');
                console.error('Ошибка:', error);
            }
        };
        
        const filterFighters = (filter) => {
            activeFilter.value = filter;
        };
        
        const scrollTo = (elementId) => {
            const element = document.getElementById(elementId);
            if (element) {
                element.scrollIntoView({ behavior: 'smooth' });
            }
        };
        
        const donateToFighter = (fighterId) => {
            donationForm.value.fighter_id = fighterId;
            showDonationModal.value = true;
            scrollTo('donate');
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
                        fighter_id: null,
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
        
        const viewFighterDetails = (fighterId) => {
            // В реальном приложении здесь будет переход на страницу бойца
            showNotification('Страница бойца будет реализована в следующей версии', 'success');
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
        
        // Инициализация при загрузке
        onMounted(() => {
            fetchData();
            
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
            fighters,
            assistanceTypes,
            urgentNeeds,
            stats,
            activeFilter,
            showDonationModal,
            donationForm,
            volunteerForm,
            donationLoading,
            volunteerLoading,
            notification,
            
            // Computed
            filteredFighters,
            
            // Методы
            filterFighters,
            scrollTo,
            donateToFighter,
            submitDonation,
            submitVolunteer,
            viewFighterDetails,
            showNotification,
            formatCurrency
        };
    }
}).mount('#app');