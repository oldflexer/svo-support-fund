import json
import os
from flask import current_app, url_for

def vite_asset(path):
    """
    Возвращает URL для ресурса, обработанного Vite.
    В режиме разработки (DEBUG=True) использует дев-сервер.
    В production читает manifest.json и ищет ключ, содержащий подстроку "{path}/main.js".
    """
    if current_app.debug:
        # В разработке используем дев-сервер Vite
        dev_paths = {
            'index': '/static/js/src/index/main.js',
            'admin': '/static/js/src/admin/main.js',
        }
        dev_path = dev_paths.get(path)
        if not dev_path:
            raise ValueError(f"Unknown dev asset: {path}. Available: {list(dev_paths.keys())}")
        return f"http://localhost:3000{dev_path}"
    else:
        # Production: читаем манифест Vite
        static_folder = current_app.static_folder
        if static_folder is None:
            raise RuntimeError("Flask static_folder is not configured")
        manifest_path = os.path.join(static_folder, 'dist', '.vite', 'manifest.json')
        if not os.path.exists(manifest_path):
            raise RuntimeError(f"Manifest not found at {manifest_path}. Run `npm run build` first.")
        
        with open(manifest_path, encoding='utf-8') as f:
            manifest = json.load(f)
        
        # 1. Пытаемся найти точное совпадение ключа (на случай коротких имён)
        if path in manifest:
            return url_for('static', filename=f'dist/{manifest[path]["file"]}')
        
        # 2. Ищем ключ, содержащий подстроку "{path}/main.js"
        search_pattern = f"{path}/main.js"  # например, "index/main.js"
        for key, value in manifest.items():
            if search_pattern in key:
                return url_for('static', filename=f'dist/{value["file"]}')
        
        # 3. Если ничего не нашли, выводим отладочную информацию
        available_keys = list(manifest.keys())
        raise ValueError(
            f"Asset '{path}' not found in manifest. "
            f"Available keys (first 10): {available_keys[:10]}"
        )