import { reactive, computed } from 'vue';

// Реактивный объект для хранения выбранного ID пользователя в фильтре логов
export const auditFilters = reactive({ user_id: null });

// Вычисляемое свойство для удобной работы с фильтром в загрузчике
export const auditUserId = computed({
    get: () => auditFilters.user_id,
    set: (v) => auditFilters.user_id = v
});