"""
Admin image upload endpoint.

This module provides a route for uploading images by admin or moderator.
Uploaded files are saved to a specified folder, and a public URL is returned.
Requires authentication and appropriate role (admin/moderator).
"""

import os
from datetime import datetime
from flask import jsonify, request, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from utils import role_required, log_action
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
        - Query parameter 'upload_folder' (str): target directory path.
        - Form-data field 'file': the image file to upload.
    Returns JSON with the public URL of the uploaded file.
    Requires authentication and admin/moderator role.
    """
    upload_folder = request.args.get('upload_folder', None, type=str)
    if upload_folder is None:
        return jsonify({'error': 'Каталог не найден'}), 400
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Пустое имя файла'}), 400
    
    if file.filename:
        filename = secure_filename(file.filename)
        # Add timestamp to avoid collisions
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{datetime.utcnow().timestamp()}{ext}"
        file.save(os.path.join(upload_folder, filename))
    
        file_url = url_for('uploaded_file', filename=filename, _external=True)
        return jsonify({'url': file_url}), 200
    
    log_action(get_jwt_identity(), 'upload_image', f'Изображение {file.filename} загружено', request.remote_addr)

    return []
