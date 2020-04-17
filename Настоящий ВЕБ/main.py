import jsonify as jsonify
from flask import Flask, request, jsonify
import logging
import json
import random

from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from flask_wtf import FlaskForm
from requests import post, get
from werkzeug.utils import redirect
from wtforms import PasswordField, SubmitField, BooleanField, StringField
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired

import house_resource
from flask import Flask, render_template
from flask_restful import Api, abort
from data import db_session
from data.house import *
from data.users import *

from flask_ngrok import run_with_ngrok

app = Flask(__name__)
run_with_ngrok(app)
logging.basicConfig(level=logging.INFO)
api = Api(app)
api.add_resource(house_resource.HouseResource, '/api/v2/func/<device_id>/<int:status>')

sessionStorage = {}
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    session = db_session.create_session()
    return session.query(User).get(user_id)


class LoginForm(FlaskForm):
    email = EmailField('Почта', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class LightModule(FlaskForm):
    title = StringField('Название модуля(называйте модуль, чтобы всегда было понятно за что он отвечает)')
    submit = SubmitField('Создать')


class RegisterForm(FlaskForm):
    email = EmailField('Почта', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    password_again = PasswordField('Повторите пароль', validators=[DataRequired()])
    name = StringField('Имя пользователя', validators=[DataRequired()])
    submit = SubmitField('Войти')


def handle_dialog(res, req):
    if 'выключи' in req['request']['command'].lower():
        print(post('http://127.0.0.1:5000/api/v2/light/0').json())
        res['response']['text'] = 'Выключила'
    else:
        print(post('http://127.0.0.1:5000/api/v2/light/1').json())
        res['response']['text'] = 'Включила'
    print()


def main():
    db_session.global_init("db/smart_house.db")
    session = db_session.create_session()

    @app.route("/", methods=['GET'])
    def start():

        session = db_session.create_session()
        if current_user.is_authenticated:
            modules = session.query(Houses).filter(Houses.user == current_user)
        else:
            modules = []
        for i in modules:
            print(i.user.name)  # Вот это
        return render_template('index.html', modules=modules, title='smart house')

    @app.route('/register', methods=['GET', 'POST'])
    def reqister():
        form = RegisterForm()
        if form.validate_on_submit():
            if form.password.data != form.password_again.data:
                return render_template('register.html', title='Регистрация',
                                       form=form,
                                       message="Пароли не совпадают")
            session = db_session.create_session()
            if session.query(User).filter(User.email == form.email.data).first():
                return render_template('register.html', title='Регистрация',
                                       form=form,
                                       message="Такой пользователь уже есть")
            user = User(name=form.name.data, email=form.email.data)
            user.set_password(form.password.data)
            session.add(user)
            session.commit()
            return redirect('/login')
        return render_template('register.html', title='Регистрация', form=form)

    @app.route('/add_light', methods=['GET', 'POST'])
    @login_required
    def add_light():
        form = LightModule()
        if form.validate_on_submit():
            module = Houses(title=form.title.data, user_id=current_user.id, status=0)
            session.add(module)
            session.commit()
            return redirect('/')
        return render_template('add_light.html', title='Добавление модуля', form=form)

    @app.route('/add_module')
    @login_required
    def add_module():
        return render_template('add_module.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            session = db_session.create_session()
            user = session.query(User).filter(User.email == form.email.data).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                return redirect("/")
            return render_template('login.html',
                                   message="Неправильный логин или пароль",
                                   form=form)
        return render_template('login.html', title='Авторизация', form=form)

    @app.route('/change_value/<device_id>/<int:status>', methods=['GET', 'POST'])
    @login_required
    def turn_light(device_id, status):
        print(post(f'http://127.0.0.1:5000/api/v2/func/{device_id}/{status}').json())
        return redirect('/')


    @app.route('/post', methods=['POST'])
    def send():
        logging.info(f'Request: {request.json!r}')
        response = {
            'session': request.json['session'],
            'version': request.json['version'],
            'response': {
                'end_session': False
            }
        }
        handle_dialog(response, request.json)
        logging.info(f'Response: {response!r}')
        return json.dumps(response)

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect("/")

    app.run()


if __name__ == '__main__':
    main()
