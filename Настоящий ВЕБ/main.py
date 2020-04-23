from collections import defaultdict

from flask import Flask, request, jsonify, render_template
import logging
import json
import random

from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from flask_wtf import FlaskForm
from werkzeug.utils import redirect
from wtforms import (PasswordField, SubmitField, BooleanField, StringField, SelectMultipleField,
                     widgets, IntegerField)
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired

import house_resource
from flask_restful import Api, abort
from data import db_session
from data.switches import *
from data.users import *
from data.groups import *

app = Flask(__name__)
# logging.basicConfig(level=logging.INFO)
api = Api(app)
# api.add_resource(house_resource.HouseResource, '/api/v2/func/<device_id>/<int:status>')

sessionStorage = defaultdict(lambda: None)
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


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class SwitchForm(FlaskForm):
    title = StringField(
        'Название модуля(называйте модуль, чтобы всегда было понятно за что он отвечает)',
        validators=[DataRequired()])
    port = IntegerField('Номер порта', validators=[DataRequired()])
    users = MultiCheckboxField('Кто может использовать (если не выбрать доступно всем)', coerce=int)
    editors = MultiCheckboxField('Кто может редактировать (если не выбрать доступно всем)',
                                 coerce=int)
    submit = SubmitField('Создать')


class RegisterForm(FlaskForm):
    email = EmailField('Почта', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    password_again = PasswordField('Повторите пароль', validators=[DataRequired()])
    name = StringField('Имя пользователя', validators=[DataRequired()])
    submit = SubmitField('Войти')


def handle_dialog(res, req):
    session = db_session.create_session()
    user_id = req['session']['user_id']
    if req['session']['new']:
        sessionStorage[user_id] = {'log_in': False, 'user': None}
    res['response']['text'] = 'Nothing'
    print(req['request']['command'], sessionStorage[user_id]['log_in'])
    res['response']['buttons'] = []
    if not sessionStorage[user_id]['log_in']:
        res['response']['text'] = 'Я не могу вам помочь, пока вы не войдете,' \
                                  'чтобы войти, введите свой email и пароль(через пробел)'
        if req['request']['command'] and len(req['request']['command'].split()) == 2:
            email, password = req['request']['command'].split()[0], req['request']['command'].split()[1]
            user = session.query(User).filter(User.email == email).first()
            print(user.name, user.check_password(password), generate_password_hash(password))
            if user and user.check_password(password):
                sessionStorage[user_id]['user'] = user
                sessionStorage[user_id]['log_in'] = True
                res['response']['text'] = 'Вы вошли'
                print(req['request']['command'], sessionStorage[user_id]['log_in'])
                return
            else:
                res['response']['text'] = 'Вы неправильно ввели логин или пароль'
        return

    elif req['request']['command'].lower() == 'выйти':
        res['response']['text'] = 'Вы вышли'
        sessionStorage[user_id]['user'] = None
        sessionStorage[user_id]['log_in'] = False
        return

    elif req['request']['command'].lower() == 'help':
        res['response']['text'] = '''Включить <Название модуля>
            Выключить <Название модуля>'''
        return

    elif 'включить' in req['request']['command'].lower():
        pos = req['request']['command'].lower().find('включить')
        target = req['request']['command'][pos + 9:].lower().strip()
        print(target)
        if target:
            res['response']['text'] = 'Не смогла найти'
            user = sessionStorage[user_id]['user']
            if len(target.split()) > 1 and target.split()[0] == 'группу':
                res['response']['text'] = 'Я ещё не работаю с группами'
            else:
                for switch in user.usable_switches:
                    if switch.title == target:
                        switch.status = True
                        res['response']['text'] = 'Включила!'
                        break
            session.commit()
            print('включила')
        else:
            res['response']['text'] = 'Что включить?'
        return

    elif 'выключить' in req['request']['command'].lower():
        pos = req['request']['command'].lower().find('включить')
        target = req['request']['command'][pos + 11:].lower().strip()
        print(target)
        if target:
            res['response']['text'] = 'Не смогла найти'
            user = sessionStorage[user_id]['user']
            if len(target.split()) > 1 and target.split()[0] == 'группу':
                res['response']['text'] = 'Я ещё не работаю с группами'
            else:
                for switch in user.usable_switches:
                    if switch.title == target:
                        switch.status = False
                        res['response']['text'] = 'Выключила!'
                        break
            session.commit()
            print('выключила')
        else:
            res['response']['text'] = 'Что выключить?'
        return
    res['response']['text'] = 'Я не знаю этой команды, чтобы узнать список команд, напишите help'


def main():
    db_session.global_init("db/smart_house.db")

    @app.route("/", methods=['GET'])
    def start():
        session = db_session.create_session()
        public_switches = session.query(Switch).filter((Switch.public_use == 1)
                                                       | (Switch.public_edit == 1)).all()
        return render_template('index.html', title='smart house', public_switches=public_switches)

    @app.route('/add_switch', methods=['GET', 'POST'])
    @login_required
    def add_switch():
        form = SwitchForm()
        session = db_session.create_session()
        all_users = [(user.id, user.name) for user in session.query(User).all()]
        form.users.choices = all_users
        form.editors.choices = all_users
        if form.validate_on_submit():
            session = db_session.create_session()
            if session.query(Switch).filter(Switch.title == form.title.data).first():
                return render_template('switch.html', title='Добавление модуля', form=form,
                                       message='Имя модуля уже занято')

            switch = Switch(title=form.title.data.lower(), status=0, port=form.port.data)
            session.add(switch)
            for user in form.users.data:
                switch.users.append(session.query(User).filter(User.id == user).first())
            for editor in form.editors.data:
                switch.editors.append(session.query(User).filter(User.id == editor).first())
            switch.public_edit = not bool(switch.editors)
            switch.public_use = not bool(switch.users)
            session.merge(switch)
            session.commit()
            return redirect('/')
        return render_template('switch.html', title='Добавление модуля', form=form)

    @app.route('/edit_switch/<int:switch_id>', methods=['GET', 'POST'])
    def edit_switch(switch_id):
        form = SwitchForm()
        session = db_session.create_session()
        all_users = [(user.id, user.name) for user in session.query(User).all()]
        form.editors.choices = all_users
        form.users.choices = all_users
        if request.method == 'GET':
            switch = session.query(Switch).filter(Switch.id == switch_id).first()
            if switch:
                if current_user in switch.editors or not switch.editors:
                    form.title.data = switch.title
                    form.port.data = switch.port
                    form.editors.data = [user.id for user in switch.editors]
                    form.users.data = [user.id for user in switch.users]
                else:
                    abort(403)
            else:
                abort(404)
        if form.validate_on_submit():
            switch = session.query(Switch).filter(Switch.id == switch_id).first()
            if switch:
                if current_user in switch.editors or not switch.editors:
                    if session.query(Switch).filter(Switch.title == form.title.data,
                                                    Switch.id != switch_id).first():
                        return render_template('switch.html', title='Редактирования модуля',
                                               form=form, message='Имя модуля уже занято')
                    switch = session.query(Switch).filter(Switch.id == switch_id).first()
                    switch.title = form.title.data
                    switch.port = form.port.data
                    for user in switch.users:
                        if user.id not in form.users.data:
                            switch.users.remove(user)
                    for user_id in form.users.data:
                        user = session.query(User).filter(User.id == user_id).first()
                        if user not in switch.users:
                            switch.users.append(user)
                    for user in switch.editors:
                        if user.id not in form.editors.data:
                            switch.editors.remove(user)
                    for user_id in form.editors.data:
                        user = session.query(User).filter(User.id ==
                                                          user_id).first()
                        if user not in switch.editors:
                            switch.editors.append(user)
                    switch.public_edit = not bool(switch.editors)
                    switch.public_use = not bool(switch.users)
                    session.merge(switch)
                    session.commit()
                    return redirect('/')
                else:
                    abort(403)
            else:
                abort(404)
        return render_template('switch.html', title='Редактирование модуля', form=form)

    @app.route('/delete_switch/<int:switch_id>', methods=['GET'])
    def delete_switch(switch_id):
        session = db_session.create_session()
        switch = session.query(Switch).filter(Switch.id == switch_id).first()
        if switch:
            if not switch.editors or current_user in switch.editors:

                session.delete(switch)
                session.commit()
            else:
                abort(403)
        else:
            abort(404)
        return redirect('/')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
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

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect("/")

    # @app.route('/change_value/<device_id>/<int:status>', methods=['GET', 'POST'])
    # @login_required
    # def turn_light(device_id, status):
    #     print(post(f'http://127.0.0.1:5000/api/v2/func/{device_id}/{status}').json())
    #     return redirect('/')

    # @app.route('/post', methods=['POST'])
    # def send():
    #     logging.info(f'Request: {request.json!r}')
    #     response = {
    #         'session': request.json['session'],
    #         'version': request.json['version'],
    #         'response': {
    #             'end_session': False
    #         }
    #     }
    #     handle_dialog(response, request.json)
    #     logging.info(f'Response: {response!r}')
    #     return json.dumps(response)

    app.run()


if __name__ == '__main__':
    main()
