// форматирование валюты
export function formatCurrency(value) {
    if (value === null || value === undefined) return '0 ₽';
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        minimumFractionDigits: 0
    }).format(value);
}

// форматирование процентов
export function formatPercent(value) {
    if (value === null || value === undefined) return '0%';
    return new Intl.NumberFormat('ru-RU', {
        style: 'percent',
        minimumFractionDigits: 0
    }).format(value);
}

// форматирование даты (Московское время)
export function formatDate(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return new Intl.DateTimeFormat('ru-RU', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Europe/Moscow'
    }).format(date);
}

// копирование в буфер обмена (используется в 2FA)
export function copyToClipboard(text, showNotification) {
    navigator.clipboard.writeText(text)
        .then(() => showNotification('Скопировано'))
        .catch(() => showNotification('Ошибка копирования', 'error'));
}