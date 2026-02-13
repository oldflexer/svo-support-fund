import unittest
from schemas import (
    LoginSchema, AdminCreateSchema, FighterCreateSchema, 
    DonationCreateSchema, validate_request_data, ValidationError
)
import json

class TestSchemas(unittest.TestCase):
    
    def test_login_schema_valid(self):
        """Test valid login data"""
        data = {
            'username': 'testuser',
            'password': 'password123'
        }
        
        try:
            validated = validate_request_data('login', data)
            self.assertEqual(validated['username'], 'testuser')
            self.assertEqual(validated['password'], 'password123')
        except ValidationError:
            self.fail('Valid data should not raise an error')
    def test_login_schema_invalid(self):
        """Test invalid login data"""
        data = {
            'username': '',  # Empty username
            'password': ''
        }
        
        with self.assertRaises(ValidationError) as context:
            validate_request_data('login', data)
        
        errors = context.exception.messages
        self.assertIn('username', errors)
        self.assertIn('password', errors)
    
    def test_admin_create_schema_valid(self):
        """Test valid admin creation data"""
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
        """Test weak password"""
        data = {
            'username': 'test',
            'email': 'test@example.com',
            'password': 'weak'  # Too short
        }
        
        with self.assertRaises(ValidationError) as context:
            validate_request_data('admin_create', data)
        
        errors = context.exception.messages
        self.assertIn('password', errors)
    
    def test_fighter_create_schema_valid(self):
        """Test valid fighter creation data"""
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
        """Test valid donation data"""
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
        """Test too small donation"""
        data = {
            'name': 'Тест',
            'amount': 50.0  # Below minimum
        }
        
        with self.assertRaises(ValidationError) as context:
            validate_request_data('donation_create', data)
        
        errors = context.exception.messages
        self.assertIn('amount', errors)
    
    def test_xss_protection(self):
        """Test XSS protection"""
        malicious_data = {
            'username': 'test',
            'password': 'password123',
            'message': '<script>alert("xss")</script>Hello'
        }
        
        # Test sanitization through sanitize_input
        from schemas import sanitize_input
        cleaned = sanitize_input(malicious_data['message'])
        self.assertNotIn('<script>', cleaned)
        self.assertIn('&lt;script&gt;', cleaned)
    
    def test_schema_missing_required(self):
        """Test missing required fields"""
        data = {
            'username': 'test'
            # password missing
        }
        
        with self.assertRaises(ValidationError) as context:
            validate_request_data('login', data)
        
        errors = context.exception.messages
        self.assertIn('password', errors)

if __name__ == '__main__':
    unittest.main()