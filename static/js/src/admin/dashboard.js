import { ref } from 'vue';
import { apiFetch } from '../api.js';
import Chart from 'chart.js/auto';

export const dashboardData = ref({
    donations: { total: 0, total_amount: 0, change: 0, recent_donations: [] },
    volunteers: { total: 0 },
    chart: { labels: [], datasets: [{ label: '', data: [] }] }
});
export const donationsChart = ref(null);
let chartInstance = null;

export async function loadDashboard() {
    try {
        const response = await apiFetch('/api/admin/dashboard');
        const data = await response.json();
        dashboardData.value = {
            donations: {
                total: data.donations.total,
                total_amount: data.donations.total_amount,
                change: data.donations.change,
                recent_donations: data.donations.recent_donations
            },
            volunteers: { total: data.volunteers.total },
            chart: {
                labels: data.chart.labels,
                datasets: [{
                    label: data.chart.datasets[0].label,
                    data: data.chart.datasets[0].data
                }]
            }
        };
        updateChart();
    } catch (e) { console.error('Dashboard load failed', e); }
}

function updateChart() {
    if (!donationsChart.value) return;
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
                backgroundColor: 'rgb(59, 130, 246)'
            }]
        },
        options: { responsive: true, maintainAspectRatio: true }
    });
}