const { createApp, ref, computed, onMounted, watch } = Vue;
const twoFactorModal = ref(false);
const twoFactorStep = ref('setup'); // 'setup', 'verify', 'enable', 'disable'
const twoFactorData = ref({});
const twoFactorForm = ref({
    token: '',
    useBackup: false,
    password: ''
});

createApp({
    setup() {
        // Состояния аутентификации
        const isAuthenticated = ref(false);
        const currentUser = ref({});
        const accessToken = ref(localStorage.getItem('access_token'));
        // const refreshToken = ref(localStorage.getItem('refresh_token'));
        
        // Форма логина
        const loginForm = ref({
            username: '',
            password: ''
        });
        const loading = ref(false);
        const loginError = ref('');
        
        // Активная вкладка
        const activeTab = ref('dashboard');
        
        // Данные
        const fighters = ref([]);
        const donations = ref({ items: [], total: 0, pages: 1, current_page: 1 });
        const adminUsers = ref([]);
        const stats = ref({});
        const recentDonations = ref([]);
        
        // Фильтры
        const fightersSearch = ref('');
        const fighterFilter = ref(null);
        const donationStatusFilter = ref('');
        
        // Уведомления
        const notification = ref({
            show: false,
            message: '',
            type: 'success',
            icon: 'fas fa-check-circle'
        });
        
        // Константы
        const API_URL = 'http://localhost:5000';
        const roleLabels = {
            'admin': 'Администратор',
            'moderator': 'Модератор',
            'viewer': 'Наблюдатель'
        };
        
        // Chart.js экземпляр
        let donationsChart = null;
        
        // Computed свойства
        const filteredFighters = computed(() => {
            let filtered = fighters.value;
            
            // Поиск
            if (fightersSearch.value) {
                const search = fightersSearch.value.toLowerCase();
                filtered = filtered.filter(f => 
                    f.call_sign.toLowerCase().includes(search) ||
                    f.unit?.toLowerCase().includes(search) ||
                    f.region?.toLowerCase().includes(search)
                );
            }
            
            // Фильтр по статусу
            if (fighterFilter.value === 'verified') {
                filtered = filtered.filter(f => f.is_verified);
            } else if (fighterFilter.value) {
                filtered = filtered.filter(f => f.status === fighterFilter.value);
            }
            
            return filtered;
        });
        
        const filteredDonations = computed(() => {
            let filtered = donations.value.items || [];
            
            if (donationStatusFilter.value) {
                filtered = filtered.filter(d => d.status === donationStatusFilter.value);
            }
            
            return filtered;
        });
        
        // Методы авторизации
        // const login = async () => {
        //     loading.value = true;
        //     loginError.value = '';
            
        //     try {
        //         const response = await fetch(`${API_URL}/api/auth/login`, {
        //             method: 'POST',
        //             headers: {
        //                 'Content-Type': 'application/json'
        //             },
        //             body: JSON.stringify(loginForm.value)
        //         });
                
        //         const data = await response.json();
                
        //         if (data.success) {
        //             // Сохраняем токены
        //             localStorage.setItem('access_token', data.access_token);
        //             localStorage.setItem('refresh_token', data.refresh_token);
        //             localStorage.setItem('user', JSON.stringify(data.user));
                    
        //             accessToken.value = data.access_token;
        //             refreshToken.value = data.refresh_token;
        //             currentUser.value = data.user;
        //             isAuthenticated.value = true;
                    
        //             showNotification('Успешный вход в систему', 'success');
                    
        //             // Загружаем данные
        //             await fetchData();
        //         } else {
        //             loginError.value = data.message;
        //             showNotification(data.message, 'error');
        //         }
        //     } catch (error) {
        //         loginError.value = 'Ошибка сети. Проверьте подключение.';
        //         showNotification('Ошибка сети', 'error');
        //         console.error('Login error:', error);
        //     } finally {
        //         loading.value = false;
        //     }
        // };
        
        const logout = () => {
            // Отправляем запрос на сервер если есть токен
            if (accessToken.value) {
                fetch(`${API_URL}/api/auth/logout`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${accessToken.value}`
                    }
                }).catch(console.error);
            }
            
            // Очищаем локальное хранилище
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('user');
            
            // Сбрасываем состояние
            isAuthenticated.value = false;
            currentUser.value = {};
            accessToken.value = null;
            refreshToken.value = null;
            
            showNotification('Вы вышли из системы', 'success');
        };
        
        const refreshToken = async () => {
            if (!refreshToken.value) {
                logout();
                return;
            }
            
            try {
                const response = await fetch(`${API_URL}/api/auth/refresh`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        refresh_token: refreshToken.value
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    localStorage.setItem('access_token', data.access_token);
                    accessToken.value = data.access_token;
                    showNotification('Токен обновлён', 'success');
                } else {
                    logout();
                }
            } catch (error) {
                console.error('Token refresh error:', error);
                logout();
            }
        };
        
        // Проверка разрешений
        const hasPermission = (roles) => {
            return roles.includes(currentUser.value.role);
        };
        
        // Методы загрузки данных
        const fetchData = async () => {
            try {
                // Загружаем статистику
                await fetchStats();
                
                // Загружаем бойцов
                await fetchFighters();
                
                // Загружаем пожертвования
                await fetchDonations();
                
                // Если админ - загружаем пользователей
                if (currentUser.value.role === 'admin') {
                    await fetchAdminUsers();
                }
                
            } catch (error) {
                console.error('Error fetching data:', error);
                showNotification('Ошибка загрузки данных', 'error');
            }
        };
        
        const fetchStats = async () => {
            const response = await fetchWithAuth(`${API_URL}/api/admin/stats`);
            if (response.success) {
                stats.value = response.stats;
                
                // Создаём график если есть данные
                if (stats.value.daily_stats && donationsChart === null) {
                    createDonationsChart();
                }
            }
        };
        
        const fetchFighters = async () => {
            const response = await fetchWithAuth(`${API_URL}/api/admin/fighters`);
            if (response.success) {
                fighters.value = response.fighters;
            }
        };
        
        const fetchDonations = async (page = 1) => {
            const response = await fetchWithAuth(
                `${API_URL}/api/admin/donations?page=${page}&per_page=20`
            );
            if (response.success) {
                donations.value = response;
                recentDonations.value = response.donations.slice(0, 5);
            }
        };
        
        const fetchAdminUsers = async () => {
            const response = await fetchWithAuth(`${API_URL}/api/admin/users`);
            if (response.success) {
                adminUsers.value = response.users;
            }
        };
        
        // Вспомогательный метод для запросов с авторизацией
        const fetchWithAuth = async (url, options = {}) => {
            if (!accessToken.value) {
                logout();
                throw new Error('No access token');
            }
            
            const defaultOptions = {
                headers: {
                    'Authorization': `Bearer ${accessToken.value}`,
                    'Content-Type': 'application/json'
                }
            };
            
            const mergedOptions = { ...defaultOptions, ...options };
            
            try {
                const response = await fetch(url, mergedOptions);
                
                // Если токен истёк, пытаемся обновить
                if (response.status === 401) {
                    await refreshToken();
                    // Повторяем запрос с новым токеном
                    mergedOptions.headers['Authorization'] = `Bearer ${accessToken.value}`;
                    const retryResponse = await fetch(url, mergedOptions);
                    const retryData = await retryResponse.json();
                    return retryData;
                }
                
                const data = await response.json();
                
                // Если всё равно ошибка авторизации - выходим
                if (!response.ok && response.status === 401) {
                    logout();
                    throw new Error('Authorization failed');
                }
                
                return data;
            } catch (error) {
                console.error('API request error:', error);
                throw error;
            }
        };
        
        // Методы управления
        const editFighter = (fighter) => {
            showNotification(`Редактирование бойца ${fighter.call_sign}`, 'success');
            // Здесь будет открытие модального окна редактирования
        };
        
        const deleteFighter = async (fighterId) => {
            if (!confirm('Вы уверены, что хотите удалить этого бойца?')) {
                return;
            }
            
            try {
                const response = await fetchWithAuth(
                    `${API_URL}/api/admin/fighters/${fighterId}`,
                    { method: 'DELETE' }
                );
                
                if (response.success) {
                    showNotification('Боец успешно удалён', 'success');
                    await fetchFighters();
                } else {
                    showNotification(response.message, 'error');
                }
            } catch (error) {
                showNotification('Ошибка удаления', 'error');
            }
        };
        
        const updateDonationStatus = async (donationId, newStatus) => {
            try {
                const response = await fetchWithAuth(
                    `${API_URL}/api/admin/donations/${donationId}/status`,
                    {
                        method: 'PUT',
                        body: JSON.stringify({ status: newStatus })
                    }
                );
                
                if (response.success) {
                    showNotification('Статус обновлён', 'success');
                } else {
                    showNotification(response.message, 'error');
                }
            } catch (error) {
                showNotification('Ошибка обновления статуса', 'error');
            }
        };
        
        const editUser = (user) => {
            showNotification(`Редактирование пользователя ${user.username}`, 'success');
            // Здесь будет открытие модального окна редактирования
        };
        
        const toggleUserStatus = async (user) => {
            try {
                const response = await fetchWithAuth(
                    `${API_URL}/api/admin/users/${user.id}`,
                    {
                        method: 'PUT',
                        body: JSON.stringify({
                            is_active: !user.is_active
                        })
                    }
                );
                
                if (response.success) {
                    showNotification(
                        `Пользователь ${user.is_active ? 'деактивирован' : 'активирован'}`,
                        'success'
                    );
                    await fetchAdminUsers();
                } else {
                    showNotification(response.message, 'error');
                }
            } catch (error) {
                showNotification('Ошибка обновления пользователя', 'error');
            }
        };
        
        // Пагинация
        const prevDonationsPage = () => {
            if (donations.value.current_page > 1) {
                fetchDonations(donations.value.current_page - 1);
            }
        };
        
        const nextDonationsPage = () => {
            if (donations.value.current_page < donations.value.pages) {
                fetchDonations(donations.value.current_page + 1);
            }
        };
        
        // Графики
        const createDonationsChart = () => {
            const ctx = document.getElementById('donationsChart');
            if (!ctx) return;
            
            const dailyStats = stats.value.daily_stats || [];
            
            donationsChart = new Chart(ctx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: dailyStats.map(stat => stat.date),
                    datasets: [{
                        label: 'Сумма пожертвований',
                        data: dailyStats.map(stat => stat.amount),
                        borderColor: 'rgb(59, 130, 246)',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return new Intl.NumberFormat('ru-RU').format(value) + ' ₽';
                                }
                            }
                        }
                    }
                }
            });
        };
        
        // Вспомогательные методы
        const setActiveTab = (tab) => {
            activeTab.value = tab;
        };
        
        const setFighterFilter = (filter) => {
            fighterFilter.value = filter;
        };
        
        const getTabTitle = () => {
            const titles = {
                'dashboard': 'Дашборд',
                'fighters': 'Управление бойцами',
                'donations': 'Пожертвования',
                'volunteers': 'Волонтёры',
                'users': 'Администраторы',
                'audit': 'Логи действий',
                'stats': 'Статистика',
                'settings': 'Настройки'
            };
            return titles[activeTab.value] || 'Панель управления';
        };
        
        const getTabDescription = () => {
            const descriptions = {
                'dashboard': 'Обзорная информация и ключевые метрики',
                'fighters': 'Управление списком бойцов и их потребностями',
                'donations': 'Просмотр и управление пожертвованиями',
                'volunteers': 'Управление волонтёрами и их активностью'
            };
            return descriptions[activeTab.value] || '';
        };
        
        const getPriorityLabel = (priority) => {
            const labels = {
                1: 'Высокий',
                2: 'Средний',
                3: 'Низкий'
            };
            return labels[priority] || 'Не указан';
        };
        
        const formatCurrency = (amount) => {
            return new Intl.NumberFormat('ru-RU').format(amount) + ' ₽';
        };
        
        const formatDate = (dateString) => {
            if (!dateString) return '—';
            const date = new Date(dateString);
            return date.toLocaleDateString('ru-RU') + ' ' + date.toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit'
            });
        };
        
        const showNotification = (message, type = 'success') => {
            notification.value = {
                show: true,
                message,
                type,
                icon: type === 'success' ? 'fas fa-check-circle' : 
                       type === 'error' ? 'fas fa-exclamation-circle' :
                       'fas fa-info-circle'
            };
            
            setTimeout(() => {
                notification.value.show = false;
            }, 5000);
        };
        
        // Инициализация при загрузке
        onMounted(async () => {
            // Проверяем, есть ли сохранённый токен
            if (accessToken.value) {
                try {
                    // Проверяем токен, получая информацию о текущем пользователе
                    const response = await fetchWithAuth(`${API_URL}/api/auth/me`);
                    
                    if (response.success) {
                        currentUser.value = response.user;
                        isAuthenticated.value = true;
                        
                        // Загружаем данные
                        await fetchData();
                    } else {
                        logout();
                    }
                } catch (error) {
                    console.error('Auto-login error:', error);
                    logout();
                }
            }
            
            // Настраиваем обновление токена каждые 30 минут
            setInterval(() => {
                if (isAuthenticated.value) {
                    refreshToken();
                }
            }, 30 * 60 * 1000);
        });
        
        // Следим за изменениями данных для обновления графиков
        watch(() => stats.value.daily_stats, () => {
            if (donationsChart && stats.value.daily_stats) {
                donationsChart.data.labels = stats.value.daily_stats.map(stat => stat.date);
                donationsChart.data.datasets[0].data = stats.value.daily_stats.map(stat => stat.amount);
                donationsChart.update();
            }
        });
		
				// Добавляем методы для работы с 2FA
		const setupTwoFactor = async () => {
			try {
				const response = await fetchWithAuth(`${API_URL}/api/auth/2fa/setup`);
				
				if (response.success) {
					twoFactorData.value = response.data;
					twoFactorStep.value = 'setup';
					twoFactorModal.value = true;
					showNotification('Настройте 2FA в приложении аутентификатора', 'success');
				} else {
					showNotification(response.message, 'error');
				}
			} catch (error) {
				showNotification('Ошибка настройки 2FA', 'error');
			}
		};

		const enableTwoFactor = async () => {
			if (!twoFactorForm.value.token) {
				showNotification('Введите код из приложения', 'error');
				return;
			}
			
			try {
				const response = await fetchWithAuth(`${API_URL}/api/auth/2fa/enable`, {
					method: 'POST',
					body: JSON.stringify({
						token: twoFactorForm.value.token
					})
				});
				
				if (response.success) {
					currentUser.value.two_factor_enabled = true;
					twoFactorModal.value = false;
					twoFactorForm.value = { token: '', useBackup: false, password: '' };
					showNotification('2FA успешно включена', 'success');
					
					// Сохраняем резервные коды
					if (twoFactorData.value.backup_codes) {
						localStorage.setItem('2fa_backup_codes', JSON.stringify(twoFactorData.value.backup_codes));
						showNotification('Сохраните резервные коды в безопасном месте!', 'warning', 10000);
					}
				} else {
					showNotification(response.message, 'error');
				}
			} catch (error) {
				showNotification('Ошибка включения 2FA', 'error');
			}
		};

		const disableTwoFactor = async () => {
			if (!twoFactorForm.value.password && !twoFactorForm.value.token) {
				showNotification('Введите пароль или код 2FA', 'error');
				return;
			}
			
			if (!confirm('Вы уверены, что хотите отключить двухфакторную аутентификацию?')) {
				return;
			}
			
			try {
				const response = await fetchWithAuth(`${API_URL}/api/auth/2fa/disable`, {
					method: 'POST',
					body: JSON.stringify({
						password: twoFactorForm.value.password,
						token: twoFactorForm.value.token
					})
				});
				
				if (response.success) {
					currentUser.value.two_factor_enabled = false;
					twoFactorModal.value = false;
					twoFactorForm.value = { token: '', useBackup: false, password: '' };
					showNotification('2FA отключена', 'success');
				} else {
					showNotification(response.message, 'error');
				}
			} catch (error) {
				showNotification('Ошибка отключения 2FA', 'error');
			}
		};

		const regenerateBackupCodes = async () => {
			if (!twoFactorForm.value.token) {
				showNotification('Введите код 2FA для подтверждения', 'error');
				return;
			}
			
			if (!confirm('Старые резервные коды будут недействительны. Продолжить?')) {
				return;
			}
			
			try {
				const response = await fetchWithAuth(`${API_URL}/api/auth/2fa/backup/regenerate`, {
					method: 'POST',
					body: JSON.stringify({
						token: twoFactorForm.value.token
					})
				});
				
				if (response.success) {
					twoFactorData.value.backup_codes = response.backup_codes;
					twoFactorForm.value.token = '';
					showNotification(response.message, 'success');
					showNotification(response.warning, 'warning', 10000);
					
					// Обновляем сохранённые коды
					localStorage.setItem('2fa_backup_codes', JSON.stringify(response.backup_codes));
				} else {
					showNotification(response.message, 'error');
				}
			} catch (error) {
				showNotification('Ошибка регенерации кодов', 'error');
			}
		};

		const downloadBackupCodes = () => {
			if (!twoFactorData.value.backup_codes) {
				showNotification('Нет резервных кодов для скачивания', 'error');
				return;
			}
			
			const codesText = twoFactorData.value.backup_codes.join('\n');
			const blob = new Blob([`Резервные коды 2FA\n\n${codesText}\n\nСохраните эти коды в безопасном месте!`], 
								 { type: 'text/plain' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `2fa-backup-codes-${currentUser.value.username}.txt`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
			
			showNotification('Резервные коды скачаны', 'success');
		};

		// Обновляем функцию login для поддержки 2FA
		const login = async () => {
			loading.value = true;
			loginError.value = '';
			
			try {
				const response = await fetch(`${API_URL}/api/auth/login`, {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json'
					},
					body: JSON.stringify(loginForm.value)
				});
				
				const data = await response.json();
				
				if (data.success) {
					if (data.two_factor_required) {
						// Требуется 2FA
						twoFactorStep.value = 'verify';
						twoFactorModal.value = true;
						twoFactorData.value.temp_token = data.temp_token;
						twoFactorData.value.username = data.username;
						showNotification('Введите код из приложения аутентификатора', 'info');
					} else {
						// Обычный вход без 2FA
						handleLoginSuccess(data);
					}
				} else {
					loginError.value = data.message;
					if (data.wait_time) {
						loginError.value += ` (подождите ${data.wait_time} секунд)`;
					}
					showNotification(data.message, 'error');
				}
			} catch (error) {
				loginError.value = 'Ошибка сети. Проверьте подключение.';
				showNotification('Ошибка сети', 'error');
				console.error('Login error:', error);
			} finally {
				loading.value = false;
			}
		};

		const verifyTwoFactor = async () => {
			if (!twoFactorForm.value.token) {
				showNotification('Введите код 2FA', 'error');
				return;
			}
			
			try {
				const response = await fetch(`${API_URL}/api/auth/2fa/verify`, {
					method: 'POST',
					headers: {
						'Content-Type': 'application/json'
					},
					body: JSON.stringify({
						temp_token: twoFactorData.value.temp_token,
						two_factor_token: twoFactorForm.value.token,
						use_backup: twoFactorForm.value.useBackup
					})
				});
				
				const data = await response.json();
				
				if (data.success) {
					handleLoginSuccess(data);
					twoFactorModal.value = false;
					twoFactorForm.value = { token: '', useBackup: false, password: '' };
				} else {
					showNotification(data.message, 'error');
				}
			} catch (error) {
				showNotification('Ошибка проверки 2FA', 'error');
			}
		};

		const handleLoginSuccess = (data) => {
			// Сохраняем токены
			localStorage.setItem('access_token', data.access_token);
			localStorage.setItem('refresh_token', data.refresh_token);
			localStorage.setItem('user', JSON.stringify(data.user));
			
			accessToken.value = data.access_token;
			refreshToken.value = data.refresh_token;
			currentUser.value = data.user;
			isAuthenticated.value = true;
			
			showNotification('Успешный вход в систему', 'success');
			
			// Загружаем данные
			fetchData();
		};

		// Добавляем в шаблон админки кнопку для управления 2FA
		// В sidebar-footer или в настройках пользователя
        
        return {
            // Состояния
            isAuthenticated,
            currentUser,
            loginForm,
            loading,
            loginError,
            activeTab,
            fighters,
            donations,
            adminUsers,
            stats,
            recentDonations,
            fightersSearch,
            fighterFilter,
            donationStatusFilter,
            notification,
            
            // Константы
            roleLabels,
            
            // Computed
            filteredFighters,
            filteredDonations,
            
            // Методы
            login,
            logout,
            refreshToken,
            hasPermission,
            setActiveTab,
            setFighterFilter,
            editFighter,
            deleteFighter,
            updateDonationStatus,
            editUser,
            toggleUserStatus,
            prevDonationsPage,
            nextDonationsPage,
            getTabTitle,
            getTabDescription,
            getPriorityLabel,
            formatCurrency,
            formatDate,
            showNotification
        };
    }
}).mount('#admin-app');