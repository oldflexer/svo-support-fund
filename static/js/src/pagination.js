import { ref, watch } from 'vue';

export function createPaginatedLoader(baseUrl, filterParams, fetchFunction, options = {}) {
    const perPage = options.perPage || 20;
    const items = ref([]);
    const total = ref(0);
    const page = ref(1);
    const pages = ref(1);

    const buildUrl = (newPage) => {
        const url = new URL(baseUrl, window.location.origin);
        url.searchParams.set('page', newPage);
        url.searchParams.set('per_page', perPage);
        for (const [key, refValue] of Object.entries(filterParams)) {
            const value = refValue.value;
            if (value !== null && value !== undefined && value !== '') {
                url.searchParams.set(key, value);
            }
        }
        return url.pathname + url.search;
    };

    const load = async (newPage = page.value) => {
        try {
            const url = buildUrl(newPage);
            const response = await fetchFunction(url);
            const data = await response.json();
            items.value = data.items || [];
            total.value = data.total || 0;
            page.value = data.page || 1;
            pages.value = data.pages || 1;
        } catch (e) {
            console.error(`Error loading ${baseUrl}:`, e);
        }
    };

    const prevPage = () => {
        if (page.value > 1) load(page.value - 1);
    };
    const nextPage = () => {
        if (page.value < pages.value) load(page.value + 1);
    };

    for (const refValue of Object.values(filterParams)) {
        if (refValue && typeof refValue === 'object' && 'value' in refValue) {
            watch(refValue, () => load(1));
        }
    }

    return { items, total, page, pages, load, prevPage, nextPage };
}