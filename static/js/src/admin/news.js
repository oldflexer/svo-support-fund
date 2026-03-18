import { ref, reactive, computed, watch } from 'vue';
import { apiFetch } from '../api.js';
import { showNotification } from './notification.js';

export const showNewsModal = ref(false);
export const newsModalMode = ref('add');
export const editingNewsId = ref(null);
export const newsForm = reactive({
    title: '', slug: '', excerpt: '', content: '', category: 'новости',
    is_verified: false, main_image: '', images: []
});
export const newsLoading = ref(false);
export const newsError = ref('');
export const slugManuallyEdited = ref(false);
export const additionalImagesLoading = ref(false);

const translitMap = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'cz', 'ч': 'ch', 'ш': 'sh', 'щ': 'shh',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
    'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'J', 'К': 'K', 'Л': 'L', 'М': 'M',
    'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
    'Ф': 'F', 'Х': 'H', 'Ц': 'Cz', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shh',
    'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
    ' ': '-', ',': '', '.': '', '!': '', '?': '', ':': '', ';': '', '"': '',
    "'": '', '(': '', ')': '', '[': '', ']': '', '{': '', '}': '', '/': '',
    '\\': '', '|': '', '@': '', '#': '', '$': '', '%': '', '^': '', '&': '',
    '*': '', '+': '', '=': '', '~': '', '`': '', '<': '', '>': ''
};

export function generateSlug(text) {
    if (!text) return '';
    return text.split('').map(ch => translitMap[ch] || '').join('')
        .replace(/-+/g, '-').replace(/^-|-$/g, '').toLowerCase();
}

watch(() => newsForm.title, (newTitle, oldTitle) => {
    if (!slugManuallyEdited.value && newTitle) {
        const generated = generateSlug(newTitle);
        if (!newsForm.slug || newsForm.slug === generateSlug(oldTitle)) {
            newsForm.slug = generated;
        }
    }
});

watch(() => newsForm.slug, (newSlug) => {
    if (newSlug && newSlug !== generateSlug(newsForm.title)) {
        slugManuallyEdited.value = true;
    }
});

watch(showNewsModal, (val) => {
    if (val && newsModalMode.value === 'add') slugManuallyEdited.value = false;
});

watch(() => newsModalMode.value, (mode) => {
    if (mode === 'edit') slugManuallyEdited.value = true;
});

export function resetNewsForm() {
    newsForm.title = ''; newsForm.slug = ''; newsForm.excerpt = '';
    newsForm.content = ''; newsForm.category = 'новости'; newsForm.is_verified = false;
    newsForm.main_image = ''; newsForm.images = []; newsError.value = '';
}

export function openAddNewsModal() {
    newsModalMode.value = 'add';
    editingNewsId.value = null;
    resetNewsForm();
    showNewsModal.value = true;
}

export function editNews(item) {
    newsModalMode.value = 'edit';
    editingNewsId.value = item.id;
    newsForm.title = item.title;
    newsForm.slug = item.slug;
    newsForm.excerpt = item.excerpt || '';
    newsForm.content = item.content || '';
    newsForm.category = item.category;
    newsForm.is_verified = item.is_verified;
    newsForm.main_image = item.main_image || '';
    newsForm.images = (item.images || []).map(img => ({ url: img.url, id: img.id }));
    showNewsModal.value = true;
}

export async function saveNews(newsLoader) {
    newsLoading.value = true;
    newsError.value = '';
    try {
        const url = newsModalMode.value === 'add' ? '/api/admin/news' : `/api/admin/news/${editingNewsId.value}`;
        const method = newsModalMode.value === 'add' ? 'POST' : 'PUT';
        const payload = {
            title: newsForm.title, slug: newsForm.slug, excerpt: newsForm.excerpt,
            content: newsForm.content, category: newsForm.category, main_image: newsForm.main_image,
            is_verified: newsForm.is_verified,
            additional_images: newsForm.images.map(img => img.url)
        };
        const response = await apiFetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Ошибка сохранения');
        }
        showNotification(newsModalMode.value === 'add' ? 'Новость создана' : 'Новость обновлена', 'success');
        showNewsModal.value = false;
        resetNewsForm();
        newsLoader?.load(newsLoader.page.value);
    } catch (e) {
        newsError.value = e.message;
    } finally {
        newsLoading.value = false;
    }
}

export function confirmDeleteNews(id, newsLoader) {
    if (confirm('Вы уверены?')) deleteNews(id, newsLoader);
}

export async function deleteNews(id, newsLoader) {
    try {
        const response = await apiFetch(`/api/admin/news/${id}`, { method: 'DELETE' });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Ошибка удаления');
        }
        showNotification('Новость удалена', 'success');
        newsLoader?.load(newsLoader.page.value);
    } catch (e) {
        showNotification(e.message, 'error');
    }
}

export async function uploadNewsImage(file) {
    const formData = new FormData();
    formData.append('file', file);
    try {
        const response = await apiFetch('/api/admin/upload?subfolder=news', { method: 'POST', body: formData });
        if (!response.ok) throw new Error('Ошибка загрузки');
        const data = await response.json();
        newsForm.main_image = data.url;
        showNotification('Изображение загружено', 'success');
    } catch (e) {
        showNotification(e.message, 'error');
    }
}

export async function uploadAdditionalImages(event) {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;
    additionalImagesLoading.value = true;
    let successCount = 0, errorCount = 0;
    try {
        for (const file of files) {
            const formData = new FormData(); formData.append('file', file);
            try {
                const response = await apiFetch('/api/admin/upload?subfolder=news', { method: 'POST', body: formData });
                if (response.ok) {
                    const data = await response.json();
                    newsForm.images.push({ url: data.url, tempId: Date.now() + Math.random() + successCount });
                    successCount++;
                } else {
                    const error = await response.json();
                    showNotification(`Ошибка загрузки файла ${file.name}: ${error.error || 'Неизвестная ошибка'}`, 'error');
                    errorCount++;
                }
            } catch (e) {
                showNotification(`Ошибка сети при загрузке файла ${file.name}`, 'error');
                errorCount++;
            }
        }
        if (successCount > 0) {
            showNotification(`Загружено изображений: ${successCount}${errorCount > 0 ? `, ошибок: ${errorCount}` : ''}`, 'success');
        }
    } finally {
        additionalImagesLoading.value = false;
        event.target.value = '';
    }
}

export function removeImage(index) {
    newsForm.images.splice(index, 1);
}