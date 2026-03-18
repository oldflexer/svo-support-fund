import { createApp, onMounted } from 'vue';
import { formatCurrency, formatDate, scrollTo } from '../utils.js';
import * as stats from './stats.js';
import * as drives from './drives.js';
import * as news from './news.js';
import * as volunteers from './volunteers.js';
import * as donations from './donations.js';
import { notification, showNotification } from './notification.js';

const app = createApp({
    delimiters: ['${', '}'],
    setup() {
        onMounted(() => {
            stats.fetchStats();
            drives.fetchDrivesForSelect();
            drives.fetchDrives(1);
            news.fetchNews(1);
        });

        return {
            ...stats,
            ...drives,
            ...news,
            ...volunteers,
            ...donations,
            notification,
            showNotification,
            formatCurrency,
            formatDate,
            scrollTo
        };
    }
});

app.mount('#app');