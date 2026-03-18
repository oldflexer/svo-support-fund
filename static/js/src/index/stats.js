import { ref } from 'vue';

export const stats = ref({ sum_donation: 0, count_volunteers: 0 });

export async function fetchStats() {
    try {
        const response = await fetch('/api/public/stats');
        stats.value = await response.json();
    } catch (e) { console.error('Failed to fetch stats', e); }
}