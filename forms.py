from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email, Optional, NumberRange, Length

class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    password = StringField('Пароль', validators=[DataRequired()])

class DonationForm(FlaskForm):
    name = StringField('Имя', validators=[DataRequired(), Length(max=100)])
    amount = IntegerField('Сумма', validators=[DataRequired(), NumberRange(min=10)])
    message = TextAreaField('Сообщение', validators=[Optional(), Length(max=500)])
    is_anonymous = BooleanField('Анонимно')

class DriveForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Описание')
    needs = TextAreaField('Необходимое (JSON)')
    status = SelectField('Статус', choices=[('активен', 'Активен'), ('завершен', 'Завершен'), ('приостановлен', 'Приостановлен')])
    collected = IntegerField('Собрано', validators=[Optional()])
    needed = IntegerField('Нужно собрать', validators=[Optional()])

class NewsForm(FlaskForm):
    title = StringField('Заголовок', validators=[DataRequired(), Length(max=200)])
    slug = StringField('Slug', validators=[DataRequired(), Length(max=200)])
    excerpt = TextAreaField('Краткое описание')
    content = TextAreaField('Содержание')
    category = SelectField('Категория', choices=[('новости', 'Новости'), ('отчёт', 'Отчёт'), ('история', 'История')])
    is_verified = BooleanField('Проверено')

class VolunteerForm(FlaskForm):
    name = StringField('ФИО', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Телефон', validators=[Optional(), Length(max=20)])
    city = StringField('Город', validators=[DataRequired(), Length(max=100)])
    skills = TextAreaField('Навыки', validators=[Optional()])
    can_deliver = BooleanField('Могу доставлять')

class UserForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = StringField('Пароль', validators=[DataRequired()])
    full_name = StringField('ФИО', validators=[Length(max=100)])
    role = SelectField('Роль', validators=[DataRequired()], choices=[('админ', 'Администратор'), ('модератор', 'Модератор')])
    is_active = BooleanField('Активирован')
    