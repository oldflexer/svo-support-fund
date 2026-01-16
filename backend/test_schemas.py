import unittest
from schemas import (
    LoginSchema, AdminCreateSchema, FighterCreateSchema, 
    DonationCreateSchema, validate_request_data, ValidationError
)
import json

class TestSchemas(unittest.TestCase):
    
    def test_login_schema_valid(self):
        """Тест валидных данных для логина"""
        data = {
            'username': 'testuser',
            'password': 'password123'
        }
        
        try:
            validated = validate_request_data('login', data)
            self.assertEqual(validated['username'], 'testuser')
            self.assertEqual(validated['password'], 'password123')
        except ValidationError:
            self.fail('Валидные данные не должны вызывать ошибку')
    
    def test_login_schema_invalid(self):
        """Тест невалидных данных для логина"""
        data = {
            'username': '',  # Пустое имя пользователя
            'password': ''
        }
        
        with self.assertRaises(ValidationError) as context:
            validate_request_data('login', data)
        
        errors = context.exception.messages
        self.assertIn('username', errors)
        self.assertIn('password', errors)
    
    def test_admin_create_schema_valid(self):
        """Тест валидных данных для создания администратора"""
        data = {
            'username': 'new_admin',
            'email': 'admin@example.com',
            'password': 'Password123',
            'role': 'moderator'
        }
        
        validated = validate_request_data('admin_create', data)
        self.assertEqual(validated['username'], 'new_admin')
        self.assertEqual(validated['email'], 'admin@example.com')
        self.assertEqual(validated['role'], 'moderator')
    
    def test_admin_create_schema_weak_password(self):
        """Тест слабого пароля"""
        data = {
            'username': 'test',
            'email': 'test@example.com',
            'password': 'weak'  # Слишком короткий
        }
        
        with self.assertRaises(ValidationError) as context:
            validate_request_data('admin_create', data)
        
        errors = context.exception.messages
        self.assertIn('password', errors)
    
    def test_fighter_create_schema_valid(self):
        """Тест валидных данных для создания бойца"""
        data = {
            'call_sign': 'Волк',
            'unit': '7-я дивизия',
            'status': 'активный',
            'needs': ['Тепловизор', 'Аптечка'],
            'priority': 1
        }
        
        validated = validate_request_data('fighter_create', data)
        self.assertEqual(validated['call_sign'], 'Волк')
        self.assertEqual(validated['status'], 'активный')
        self.assertEqual(validated['priority'], 1)
        self.assertEqual(len(validated['needs']), 2)
    
    def test_donation_create_schema_valid(self):
        """Тест валидных данных для пожертвования"""
        data = {
            'name': 'Иван Иванов',
            'amount': 1000.0,
            'message': 'Поддерживаю наших героев!'
        }
        
        validated = validate_request_data('donation_create', data)
        self.assertEqual(validated['name'], 'Иван Иванов')
        self.assertEqual(validated['amount'], 1000.0)
        self.assertEqual(validated['message'], 'Поддерживаю наших героев!')
    
    def test_donation_create_schema_small_amount(self):
        """Тест слишком маленького пожертвования"""
        data = {
            'name': 'Тест',
            'amount': 50.0  # Меньше минимального
        }
        
        with self.assertRaises(ValidationError) as context:
            validate_request_data('donation_create', data)
        
        errors = context.exception.messages
        self.assertIn('amount', errors)
    
    def test_xss_protection(self):
        """Тест защиты от XSS"""
        malicious_data = {
            'username': 'test',
            'password': 'password123',
            'message': '<script>alert("xss")</script>Hello'
        }
        
        # Тестируем очистку через sanitize_input
        from schemas import sanitize_input
        cleaned = sanitize_input(malicious_data['message'])
        self.assertNotIn('<script>', cleaned)
        self.assertIn('&lt;script&gt;', cleaned)
    
    def test_schema_missing_required(self):
        """Тест отсутствия обязательных полей"""
        data = {
            'username': 'test'
            # password отсутствует
        }
        
        with self.assertRaises(ValidationError) as context:
            validate_request_data('login', data)
        
        errors = context.exception.messages
        self.assertIn('password', errors)

if __name__ == '__main__':
    unittest.main()