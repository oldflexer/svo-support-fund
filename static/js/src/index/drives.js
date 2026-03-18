import { ref, computed } from 'vue';

export const drives = ref({ items: [] });
export const drivesFilter = ref('активен');
export const drivesPage = ref(1);
export const drivesPerPage = ref(3);
export const drivesTotalPages = ref(1);
export const drivesList = ref([]);
export const selectedDriveId = ref(null);

export const filteredDrives = computed(() => {
    if (!drivesFilter.value) return drives.value.items;
    return drives.value.items.filter(item => item.status === drivesFilter.value);
});

export async function fetchDrives(page = drivesPage.value) {
    try {
        let url = `/api/public/drives?page=${page}&per_page=${drivesPerPage.value}`;
        if (drivesFilter.value) url += `&status=${encodeURIComponent(drivesFilter.value)}`;
        const res = await fetch(url);
        const data = await res.json();
        drives.value = data;
        drivesTotalPages.value = data.pages;
        drivesPage.value = data.page;
    } catch (e) { console.error(e); }
}

export function prevDrivesPage() {
    if (drivesPage.value > 1) fetchDrives(drivesPage.value - 1);
}
export function nextDrivesPage() {
    if (drivesPage.value < drivesTotalPages.value) fetchDrives(drivesPage.value + 1);
}
export function setDrivesFilter(filter) {
    drivesFilter.value = filter;
    drivesPage.value = 1;
    fetchDrives(1);
}

export async function fetchDrivesForSelect() {
    try {
        const res = await fetch('/api/public/drives?status=активен');
        const data = await res.json();
        drivesList.value = data.items || [];
    } catch (e) { console.error(e); }
}