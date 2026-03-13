"""
Admin image upload endpoint.

This module provides a route for uploading images by admin or moderator.
Uploaded files are saved to a specified folder, and a public URL is returned.
Requires authentication and appropriate role (admin/moderator).
"""

import os
from datetime import datetime
from flask import jsonify, request, url_for, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from utils import role_required, log_action, is_allowed_image
from . import admin_bp

# -------------------------------
# API: Image upload
# -------------------------------

@admin_bp.route('/upload', methods=['POST'])
@jwt_required()
@role_required('admin', 'moderator')
def upload_image():
    """
    Upload an image file.
    Expects:
        - Form-data field 'file': the image file to upload.
        - Optional query parameter 'subfolder' (e.g., 'news', 'drives').
    Returns JSON with the public URL of the uploaded file.
    Requires authentication and admin/moderator role.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не указан'}), 400

    file = request.files['file']
    if file.filename is None:
        return jsonify({'error': 'Имя файла отсутствует'}), 400
    if file.filename == '':
        return jsonify({'error': 'Пустое имя файла'}), 400

    subfolder = request.args.get('subfolder', '')
    if subfolder:
        if not subfolder.replace('_', '').isalnum():
            return jsonify({'error': 'Недопустимое имя подпапки'}), 400
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    else:
        upload_path = current_app.config['UPLOAD_FOLDER']

    os.makedirs(upload_path, exist_ok=True)

    is_valid, error_msg = is_allowed_image(file, file.filename)
    if not is_valid:
        return jsonify({'error': 'Недопустимое содержимое файла'}), 400

    filename = secure_filename(file.filename)
    name, ext = os.path.splitext(filename)
    timestamp = int(datetime.utcnow().timestamp())
    new_filename = f"{name}_{timestamp}{ext}"
    full_path = os.path.join(upload_path, new_filename)

    file.save(full_path)

    if subfolder:
        file_url = url_for('uploaded_file', filename=f"{subfolder}/{new_filename}", _external=True)
    else:
        file_url = url_for('uploaded_file', filename=new_filename, _external=True)

    log_action(get_jwt_identity(), 'upload_image', f'Изображение {new_filename} загружено', request.remote_addr)

    return jsonify({'url': file_url}), 200
