import { ref, computed } from 'vue';

export const news = ref({ items: [] });
export const featuredArticle = ref(null);
export const newsFilter = ref('');
export const newsPage = ref(1);
export const newsPerPage = ref(4);
export const newsTotalPages = ref(1);

export const filteredNews = computed(() => {
    if (!newsFilter.value) return news.value.items;
    return news.value.items.filter(item => item.category === newsFilter.value);
});

export async function fetchNews(page = newsPage.value) {
    try {
        let url = `/api/public/news?page=${page}&per_page=${newsPerPage.value}`;
        if (newsFilter.value) url += `&category=${encodeURIComponent(newsFilter.value)}`;
        const res = await fetch(url);
        const data = await res.json();
        news.value = data;
        newsTotalPages.value = data.pages;
        newsPage.value = data.page;
        featuredArticle.value = data.items?.length ? data.items[0] : null;
    } catch (e) { console.error(e); }
}

export function prevNewsPage() {
    if (newsPage.value > 1) fetchNews(newsPage.value - 1);
}
export function nextNewsPage() {
    if (newsPage.value < newsTotalPages.value) fetchNews(newsPage.value + 1);
}
export function setNewsFilter(filter) {
    newsFilter.value = filter;
    newsPage.value = 1;
    fetchNews(1);
}

export function categoryPlaceholder(category) {
    const map = { 'новости': '../static/img/news.png', 'отчёт': '../static/img/reports.png', 'история': '../static/img/tales.png' };
    return map[category] || '../static/img/news.png';
}

export function getCategoryName(cat) {
    const map = { 'новости': 'Новости', 'отчёт': 'Отчёт', 'история': 'История' };
    return map[cat] || cat;
}

export function viewArticle(slug) {
    window.location.href = `/news/${slug}`;
}