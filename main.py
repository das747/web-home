from collections import defaultdict

import socketio
from flask_socketio import emit
from requests import post
import logging
import json
import os

from flask import Flask, request, render_template
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from flask_wtf import FlaskForm
from werkzeug.utils import redirect
from wtforms import (PasswordField, SubmitField, BooleanField, StringField, SelectMultipleField,
                     widgets, IntegerField, SelectField)
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired

import autodeploy
from api import house_resource, user_resource, switch_resource, group_resource
from flask_restful import Api, abort
from data import db_session
from data.switches import Switch
from data.users import User
from data.groups import Group
from data.houses import House

sio = socketio.Server(async_mode='threading')
app = Flask(__name__)
app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'

logging.basicConfig(level=logging.INFO, format='%(filename)s --> %(levelname)s: %(message)s')

api = Api(app)  # подключение flask_restful api
app.register_blueprint(autodeploy.blueprint)
api.add_resource(house_resource.HouseResource, '/api/house/<int:house_id>')
api.add_resource(house_resource.HouseListResource, '/api/house')
api.add_resource(user_resource.UserResource, '/api/user/<int:user_id>')
api.add_resource(user_resource.UserListResource, '/api/user')
api.add_resource(switch_resource.SwitchResource, '/api/switch/<int:switch_id>')
api.add_resource(switch_resource.SwitchListResource, '/api/switch')
api.add_resource(group_resource.GroupResource, '/api/group/<int:group_id>')
api.add_resource(group_resource.GroupListResource, '/api/group')
# хранилище данных о диалогах с пользователями
sessionStorage = defaultdict(lambda: None)

login_manager = LoginManager()
login_manager.init_app(app)

# подключение к базе данных
if not os.access('./db', os.F_OK):
    os.mkdir('./db')
db_session.global_init('db/smart_house.db')


@login_manager.user_loader
def load_user(user_id):
    session = db_session.create_session()
    return session.query(User).get(user_id)


class LoginForm(FlaskForm):  # форма для авторизации пользователей
    email = EmailField('Почта', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class MultiCheckboxField(SelectMultipleField):  # поле с выпадающими чекбоксами
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class SwitchForm(FlaskForm):  # форма для добавления и редактирования модулей
    title = StringField(
        'Название модуля(называйте модуль, чтобы всегда было понятно за что он отвечает)',
        validators=[DataRequired()])
    personal_name = IntegerField('Уникальное имя устройства', validators=[DataRequired()])
    users = MultiCheckboxField('Кто может использовать (если не выбрать доступно всем)', coerce=int)
    editors = MultiCheckboxField('Кто может редактировать (если не выбрать доступно всем)',
                                 coerce=int)
    submit = SubmitField('Сохранить')


class HouseEditForm(FlaskForm):  # форма для редактирования домов
    title = StringField('Название', validators=[DataRequired()])
    address = StringField('WebHook адрес', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class HouseLoginForm(FlaskForm):
    unic_name = StringField('Уникальный адрес дома', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')


class GroupForm(FlaskForm):  # форма для добавления и редактирования групп модулей
    title = StringField('Название', validators=[DataRequired()])
    switches = MultiCheckboxField('Выбор модулей', coerce=int)
    users = MultiCheckboxField('Кто может использовать (если не выбрать доступно всем)', coerce=int)
    editors = MultiCheckboxField('Кто может редактировать (если не выбрать доступно всем)',
                                 coerce=int)
    submit = SubmitField('Сохранить')


class HouseRegisterForm(FlaskForm):  # форма для добавления домов
    title = StringField('Название', validators=[DataRequired()])
    address = StringField('WebHook адрес', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    password_again = PasswordField('Повторите пароль', validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class RegisterForm(FlaskForm):  # форма для регистрации пользователей
    email = EmailField('Почта', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    password_again = PasswordField('Повторите пароль', validators=[DataRequired()])
    name = StringField('Имя пользователя', validators=[DataRequired()])
    # house_id = SelectField('Дом', coerce=int)
    # house_password = PasswordField('Пароль от дома', validators=[DataRequired()])
    submit = SubmitField('Регистрация')


class UserEditForm(FlaskForm):  # форма для редактирования пользователей
    email = StringField('Почта', validators=[DataRequired()])
    name = StringField('Имя', validators=[DataRequired()])
    password_again = PasswordField('Введите новый пароль для смены текущего')
    password_again_2 = PasswordField('Повторите новый пароль')
    password = PasswordField('Текущий пароль', validators=[DataRequired()])
    submit = SubmitField('Сохранить')


# обработка запроса пользователя и генерация ответа для Алисы
def handle_dialog(res, req):
    session = db_session.create_session()
    user_id = req['session']['user_id']
    if req['session']['new']:
        sessionStorage[user_id] = {'log_in': False, 'user': None}
        res['response']['text'] = 'Привет, я помощник для умного дома'
        return
    elif sessionStorage[user_id]['log_in']:  # обновление объекта пользователя
        sessionStorage[user_id]['user'] = session.query(User).filter(User.id ==
                                                                     sessionStorage[user_id]['user'].id).first()
    res['response']['text'] = 'Nothing'
    res['response']['buttons'] = []
    # обработка запроса "помощь"
    if req['request']['command'].lower() in ['помощь', 'что ты умеешь']:
        res['response']['text'] = 'Я навык, который поможет вам в управлении умным домом.' \
                                  'Я могу включить и выключать модули умного дома, ' \
                                  'сообщать вам информацию о их состоянии. ' \
                                  'Для начала работы, вам необходимо зарегистрироваться на сайте ' \
                                  'http://84.201.144.114/register'
        return
    # обработка запроса неавторизированного пользователя
    if not sessionStorage[user_id]['log_in']:
        res['response']['text'] = 'Я не могу вам помочь, пока вы не войдете,' \
                                  'чтобы войти, введите свой email и пароль(через пробел)'
        #  обработка попытки автризации
        if req['request']['command'] and len(req['request']['command'].split()) == 2:
            email, password = req['request']['command'].split()[0], \
                              req['request']['command'].split()[1]
            user = session.query(User).filter(User.email == email).first()
            # print(user.name, user.check_password(password), generate_password_hash(password))
            if user and user.check_password(password):
                sessionStorage[user_id]['user'] = user
                sessionStorage[user_id]['log_in'] = True
                res['response']['text'] = '''Вы вошли
                чтобы узнать список команд напишите Help'''
                res['response']['buttons'] = [
                    {
                        'title': 'Выйти',
                        'hide': True
                    },
                    {
                        'title': 'Help',
                        'hide': True
                    },
                    {
                        'title': 'Состояние модулей',
                        'hide': True
                    }
                ]

                print(req['request']['command'], sessionStorage[user_id]['log_in'])
            else:
                res['response']['text'] = 'Вы неправильно ввели логин или пароль'
        return

    res['response']['buttons'] = [
        {
            'title': 'Выйти',
            'hide': True
        },
        {
            'title': 'Help',
            'hide': True
        },
        {
            'title': 'Состояние модулей',
            'hide': True
        }
    ]

    # обработка запроса выйти из учётной записи
    if req['request']['command'].lower() == 'выйти':
        res['response']['text'] = 'Вы вышли'
        sessionStorage[user_id]['user'] = None
        sessionStorage[user_id]['log_in'] = False
        res['response']['buttons'] = []
        return

    # обработка запроса списка команд
    if req['request']['command'].lower() == 'help':
        res['response']['text'] = '''Включить <Название модуля>
            Выключить <Название модуля>
            Включить группу <Название группы>
            Выключить группу <Название группы>
            Состояние модулей(список модулей и их состояние)'''
        return

    # обрабокта запроса вывода состояния модулей
    if 'состояние модулей' in req['request']['command'].lower():
        res['response']['text'] = ''
        user = sessionStorage[user_id]['user']
        if not user.usable_switches and not session.query(Switch).filter(Switch.public_use == 1):
            res['response']['text'] = 'У вас нет модулей умного дома'
        print(user.usable_switches)

        switches = user.usable_switches
        for switch in session.query(Switch).filter(Switch.public_use == 1):
            switches.append(switch)
        print(set(switches))
        for switch in switches:
            module = session.query(Switch).filter(Switch.id == switch.id).first()
            res['response']['text'] += str(
                module.title) + ': ' + 'включен' * module.status + 'выключен' * (
                                               1 - module.status) + '\n'

        return

    # обработка запроса включения
    if 'включить' in req['request']['command'].lower():
        session = db_session.create_session()
        pos = req['request']['command'].lower().find('включить')
        target = req['request']['command'][pos + 9:].lower().strip()
        print(target)
        if target:
            user = sessionStorage[user_id]['user']
            # включение группы
            if len(target.split()) > 1 and target.split()[0] == 'группу':
                target = target[7:]
                session = db_session.create_session()
                group = session.query(Group).filter(Group.title == target).first()
                if group is None:
                    res['response']['text'] = 'Я не смогла найти такую группу, возможно вы ввели' \
                                              ' неправильное название группы,' \
                                              ' или вы не можете ей управлять'
                    return
                if sessionStorage[user_id]['user'] in group.users or group.public_use:
                    for switch in group.switches:
                        switch.status = True
                    group.status = True
                    session.merge(group)
                    session.commit()
                    res['response']['text'] = 'Включаю!'
                return

            else:  # включение одного модуля
                for switch in user.usable_switches:
                    if switch.title == target:
                        module = session.query(Switch).filter(Switch.id == switch.id).first()
                        module.status = True
                        res['response']['text'] = 'Включила!'
                        session.commit()
                        print(module.title)
                        print(module.status)
                        return

                print('включила')
        else:
            res['response']['text'] = 'Что включить?'
            return

    # обработка запроса выключения
    elif 'выключить' in req['request']['command'].lower():
        session = db_session.create_session()
        pos = req['request']['command'].lower().find('выключить')
        target = req['request']['command'][pos + 10:].lower().strip()
        print(target)
        if target:
            res['response']['text'] = 'Не смогла найти'
            user = sessionStorage[user_id]['user']
            # выключение группы
            if len(target.split()) > 1 and target.split()[0] == 'группу':
                target = target[7:]
                session = db_session.create_session()
                group = session.query(Group).filter(Group.title == target).first()
                if group is None:
                    res['response']['text'] = 'Я не смогла найти такую группу, возможно вы ввели' \
                                              ' неправильное название группы,' \
                                              ' или вы не можете ей управлять'
                    return
                if sessionStorage[user_id]['user'] in group.users or group.public_use:
                    for switch in group.switches:
                        switch.status = False
                    group.status = False
                    session.merge(group)
                    session.commit()
                    res['response']['text'] = 'Выключаю!'
            else:  # выключение одного модуля
                for switch in user.usable_switches:
                    if switch.title == target:
                        module = session.query(Switch).filter(Switch.id == switch.id).first()
                        module.status = False
                        res['response']['text'] = 'Выключила!'
                        session.commit()
                        print(module.title)
                        print(module.status)
                        return

                print('выключила')
        else:
            res['response']['text'] = 'Что выключить?'
        return
    res['response']['text'] = 'Я не знаю этой команды, чтобы узнать список команд, напишите help'


# обработчик стартовой страницы со списком модулей
@app.route("/", methods=['GET'])
def start_page():
    session = db_session.create_session()
    if current_user.is_authenticated:
        if current_user.house_id == 0:
            return redirect("/login_house")
        user = session.query(User).filter(User.id == current_user.id).first()
        public = session.query(Switch).filter((Switch.public_edit == 1) |
                                              (Switch.public_use == 1),
                                              Switch.house_id == user.house_id).all()
        # удаление дубликатов
        switches = sorted({*user.usable_switches, *user.editable_switches, *public},
                          key=lambda s: s.id)
    else:
        switches = []
    return render_template('index.html', title='Smart house', items=switches, type='switch')

#  Обрботчик вторизации в доме
@app.route("/login_house", methods=['GET', 'POST'])
@login_required
def home_page():
    form = HouseLoginForm()
    session = db_session.create_session()
    if current_user.is_authenticated:
        if request.method == 'GET':
            return render_template('house_login.html', title='Авторизация в доме', form=form)
        elif form.validate_on_submit():
            house = session.query(House).filter(House.web_hook == form.unic_name.data).first()
            if not house:
                return render_template('house_login.html', title='Авторизация в доме', form=form,
                                       message="Такого дома нет")
            elif not house.check_password(form.password.data):
                return render_template('house_login.html', title='Авторизация в доме', form=form,
                                       message="Пароль неверный")
            user = session.query(User).filter(User.id == current_user.id).first()
            user.house_id = house.id
            session.commit()
            return redirect('/')
    else:
        abort(403)

#  Обработчик выхода из умного дома
@app.route('/logout_house')
@login_required
def logout_house():
    session = db_session.create_session()
    user = session.query(User).get(current_user.id)
    if user:
        user.house_id = 0
        session.commit()
        return redirect('/')
    else:
        abort(404)


# обработчик страницы редактирования проиля пользователя
@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    form = UserEditForm()
    session = db_session.create_session()
    user = session.query(User).get(user_id)
    if user:  # проверка существования
        if user_id == current_user.id:  # проверка прав на редактирование
            if request.method == 'GET':

                form.name.data = user.name
                form.email.data = user.email
                return render_template('user.html', title='Редактирование пользователя', form=form,
                                       item=user)

            elif form.validate_on_submit():
                # print(form.password_again.data, form.password_again_2.data)
                # проверка уникальности почты
                if session.query(User).filter(User.email == form.email.data, User.id != user_id).first():
                    return render_template('user.html', title='Редактирование пользователя',
                                           form=form, message="Такая почта уже зарегистрирована",
                                           item=user)
                # проверка подлинности пароля
                elif not user.check_password(form.password.data):
                    return render_template('user.html', form=form,
                                           title='Редактирование пользователя',
                                           message='Пароли не совпадают', item=user)
                # проверка совпадения новых паролей
                elif form.password_again.data != form.password_again_2.data:
                    print(form.password_again.data, form.password_again_2.data)
                    return render_template('user.html', form=form,
                                           title='Редактирование пользователя',
                                           message='Пароли не совпадают', item=user)

                user.name = form.name.data
                user.email = form.email.data
                if form.password_again.data != '':
                    user.set_password(form.password_again.data)
                session.commit()
                return redirect('/')
        else:
            abort(403)
    else:
        abort(404)


# обрботчик удаления пользователя
@app.route('/delete_user/<int:user_id>', methods=['GET'])
@login_required
def delete_user(user_id):
    session = db_session.create_session()
    user = session.query(User).get(user_id)
    if user:  # проверка существования
        if current_user.id == user.id:  # проверка прав
            logout_user()
            session.delete(user)
            session.commit()
            return redirect('/')
        else:
            abort(403)
    else:
        abort(404)


# обработчик страницы создания модуля
@app.route('/add_switch', methods=['GET', 'POST'])
@login_required
def add_switch():
    form = SwitchForm()
    session = db_session.create_session()
    # заполнение вариантов для выпадающих чекбоксов
    all_users = [(user.id, user.name) for user in
                 session.query(User).filter(User.house_id == current_user.house_id).all()]
    form.users.choices = all_users
    form.editors.choices = all_users
    if form.validate_on_submit():
        # проверка уникальности названия
        if session.query(Switch).filter(Switch.title == form.title.data,
                                        Switch.house_id == current_user.house_id).first():
            return render_template('switch.html', title='Добавление модуля', form=form,
                                   message='Имя модуля уже занято')
        # проверка уникальности порта
        elif session.query(Switch).filter(Switch.personal_name == form.personal_name.data,
                                          Switch.house_id == current_user.house_id).first():
            return render_template('switch.html', title='Добавление модуля', form=form,
                                   message='Этот порт уже используется')

        switch = Switch(title=form.title.data.lower(), status=0, personal_name=form.personal_name.data,
                        house_id=current_user.house_id)
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


# обработчик страницы редактировнаия пользователя
@app.route('/edit_switch/<int:switch_id>', methods=['GET', 'POST'])
@login_required
def edit_switch(switch_id):
    form = SwitchForm()
    session = db_session.create_session()
    # заполнение вариантов для выпадающих чекбоксов
    all_users = [(user.id, user.name) for user in
                 session.query(User).filter(User.house_id == current_user.house_id).all()]
    form.editors.choices = all_users
    form.users.choices = all_users
    switch = session.query(Switch).filter(Switch.id == switch_id).first()
    if switch:  # проверка существования
        if current_user in switch.editors or switch.public_edit:  # проверка прав
            if request.method == 'GET':
                form.title.data = switch.title
                form.personal_name.data = switch.personal_name
                form.editors.data = [user.id for user in switch.editors]
                form.users.data = [user.id for user in switch.users]
                return render_template('switch.html', title='Редактирование модуля', form=form,
                                       item=switch)

            elif form.validate_on_submit():
                # проверка ункальности названия
                if session.query(Switch).filter(Switch.title == form.title.data,
                                                Switch.id != switch_id,
                                                Switch.house_id == switch.house_id).first():
                    return render_template('switch.html', title='Редактирования модуля',
                                           form=form, message='Имя модуля уже занято', item=switch)
                # проверка уникальности порта
                elif session.query(Switch).filter(Switch.personal_name == form.personal_name.data,
                                                  Switch.id != switch_id,
                                                  Switch.house_id == switch.house_id).first():
                    return render_template('switch.html', title='Редактирования модуля',
                                           form=form, message='"Этот порт уже используется"',
                                           item=switch)
                switch.title = form.title.data
                switch.personal_name = form.personal_name.data
                # изменение списка пользователей:
                for user in switch.users:  # удаление лишних
                    if user.id not in form.users.data:
                        switch.users.remove(user)
                for user_id in form.users.data:  # добавление новых
                    user = session.query(User).filter(User.id == user_id).first()
                    if user not in switch.users:
                        switch.users.append(user)

                # изменение списка редакторов:
                for user in switch.editors:  # удаление лишних
                    if user.id not in form.editors.data:
                        switch.editors.remove(user)
                for user_id in form.editors.data:  # добавление новых
                    user = session.query(User).filter(User.id == user_id).first()
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


# обработчик удаления модуля
@app.route('/delete_switch/<int:switch_id>', methods=['GET'])
@login_required
def delete_switch(switch_id):
    session = db_session.create_session()
    switch = session.query(Switch).filter(Switch.id == switch_id).first()
    if switch:  # проверка существования
        if switch.public_edit or current_user in switch.editors:  # проверка прав
            session.delete(switch)
            session.commit()
            return redirect('/')
        else:
            abort(403)
    else:
        abort(404)


# обработчик изменения состояния модуля
@app.route('/set_switch/<int:device_id>/<int:state>', methods=['GET', 'POST'])
@login_required
def turn_light(device_id, state):
    session = db_session.create_session()
    user = session.query(User).filter(User.id == current_user.id).first()
    switch = session.query(Switch).filter(Switch.id == device_id).first()
    if switch:  # проверка существования
        if switch.public_use or user in switch.users:  # проверка прав
            switch.status = state
            if not state:
                for group in switch.groups:
                    group.status = state
            session.commit()
            # отправка запроса на управляющее устройство
            # post(switch.house.web_hook, json={'port': switch.port, 'status': switch.status})
        else:
            abort(403)
    else:
        abort(404)
    if switch.sid != 0:
        sio.emit('get_msg', {'status': switch.status}, room=switch.sid)
    return redirect("/")


# обработчик стрницы добавления дома
@app.route('/add_house', methods=['GET', 'POST'])
def add_house():
    form = HouseRegisterForm()
    if form.validate_on_submit():
        session = db_session.create_session()
        # проверка уникальности названия
        if session.query(House).filter(House.title == form.title.data).first():
            return render_template('house.html', form=form, title='Добавление дома',
                                   message='Имя дома уже занято')
        # проверка уникальноти адреса
        elif session.query(House).filter(House.web_hook == form.address.data).first():
            return render_template('house.html', form=form, title='Добавление дома',
                                   message='Дом с таким адресом уже добавлен')
        # проверка совпадения паролей
        elif form.password.data != form.password_again.data:
            return render_template('house.html', form=form, title='Добавление дома',
                                   message='Пароли не совпадают')
        else:
            house = House(title=form.title.data, web_hook=form.address.data)
            house.set_password(form.password.data)
            session.add(house)
            session.commit()
            return redirect('/register')
    return render_template('house.html', form=form, title='Добавление дома')


# обработчик страницы редактирования дома
@app.route('/edit_house/<int:house_id>', methods=['GET', 'POST'])
@login_required
def edit_house(house_id):
    form = HouseEditForm()
    session = db_session.create_session()
    house = session.query(House).filter(House.id == house_id).first()
    user = session.query(User).filter(User.id == current_user.id).first()
    if house:  # проверка существования
        if house.id == user.house.id:  # проверка прав
            if request.method == 'GET':
                form.address.data = house.web_hook
                form.title.data = house.title
                return render_template('house.html', title='Редактирование дома', form=form)
            elif form.validate_on_submit():
                # проверка уникальности названия
                if session.query(House).filter(House.title == form.title.data,
                                               House.id != house_id).first():
                    return render_template('house.html', title='Редактирование дома', form=form,
                                           message='Имя дома уже занято')
                # проверка уникальности адреса
                elif session.query(House).filter(House.web_hook == form.address.data,
                                                 House.id != house_id).first():
                    return render_template('house.html', title='Редактирование дома', form=form,
                                           message='Дом с таким адресом уже существует')
                # проверка подлинности пароля
                elif not house.check_password(form.password.data):
                    return render_template('house.html', title='Редактирование дома', form=form,
                                           message='Указан неверный пароль')
                house.title = form.title.data
                house.web_hook = form.address.data
                session.commit()
                return redirect('/')
        else:
            abort(403)
    else:
        abort(404)


# обработчик страницы со списком групп модулей
@app.route('/groups_list')
def list_groups():
    session = db_session.create_session()
    user = session.query(User).filter(User.id == current_user.id).first()
    if current_user.is_authenticated and user.house_id != 0:
        user = session.query(User).filter(User.id == current_user.id).first()
        public = session.query(Group).filter((Group.public_edit == 1) |
                                             (Group.public_use == 1),
                                             Group.house_id == user.house_id).all()
        # удаление дубликатов
        groups = sorted({*user.usable_groups, *user.editable_groups, *public},
                        key=lambda s: s.id)
    else:
        groups = []
    return render_template('index.html', title='Smart house', items=groups, type='group')


# обработчик страницы добавления группы модулей
@app.route('/add_group', methods=['GET', 'POST'])
@login_required
def add_group():
    session = db_session.create_session()
    user = session.query(User).filter(User.id == current_user.id).first()
    form = GroupForm()
    # заполнение вариантов выпадающих чекбоксов
    house_users = [(user.id, user.name) for user in
                   session.query(User).filter(User.house_id == user.house_id).all()]
    form.users.choices = house_users
    form.editors.choices = house_users
    usable_switches = user.usable_switches + session.query(Switch).filter(Switch.public_use == 1,
                                                                          Switch.house_id == user.house_id).all()
    form.switches.choices = [(s.id, s.title) for s in usable_switches]
    if form.validate_on_submit():
        # проверка уникальности названия
        if session.query(Group).filter(Group.title == form.title.data,
                                       Group.house_id == user.house_id).first():
            return render_template('group.html', title='Добавление группы', form=form,
                                   message='Имя группы уже занято')
        # проверка что группа не пустая
        elif not form.switches.data:
            return render_template('group.html', title='Добавление группы', form=form,
                                   message='Не выбран ни один модуль')
        group = Group(title=form.title.data.lower(), house_id=user.house_id)
        session.add(group)
        for user_id in form.editors.data:
            group.editors.append(session.query(User).filter(User.id == user_id).first())
        for user_id in form.users.data:
            group.users.append(session.query(User).filter(User.id == user_id).first())
        for switch_id in form.switches.data:
            group.switches.append(session.query(Switch).filter(Switch.id == switch_id).first())
        group.public_use = not bool(group.users)
        group.public_edit = not bool(group.editors)
        session.merge(group)
        session.commit()
        return redirect('/groups_list')
    return render_template('group.html', title='Добавление группы', form=form)


# обработчик страницы редактирования группы модулей
@app.route('/edit_group/<int:group_id>', methods=['GET', 'POST'])
@login_required
def edit_group(group_id):
    form = GroupForm()
    session = db_session.create_session()
    user = session.query(User).filter(User.id == current_user.id).first()
    # добавление вариантов выпадающих чекбоксов
    all_users = [(user.id, user.name) for user in
                 session.query(User).filter(User.house_id == current_user.house_id).all()]
    form.editors.choices = all_users
    form.users.choices = all_users
    usable_switches = user.usable_switches + session.query(Switch).filter(Switch.public_use == 1,
                                                                          Switch.house_id == user.house_id).all()
    form.switches.choices = [(s.id, s.title) for s in usable_switches]
    group = session.query(Group).filter(Group.id == group_id).first()
    if group:  # проверка существования
        if current_user in group.editors or group.public_edit:  # проверка прав
            if request.method == 'GET':
                form.title.data = group.title
                form.editors.data = [user.id for user in group.editors]
                form.users.data = [user.id for user in group.users]
                form.switches.data = [switch.id for switch in group.switches]
                return render_template('group.html', title='Редактирование группы', form=form,
                                       item=group)

            elif form.validate_on_submit():
                # проверка уникальности названия
                if session.query(Group).filter(Group.title == form.title.data,
                                               Group.id != group_id,
                                               Group.house_id == group.house_id).first():
                    return render_template('group.html', title='Редактирования группы',
                                           form=form, message='Имя группы уже занято', item=group)
                # проверка что группа не пустая
                elif not form.switches.data:
                    return render_template('group.html', title='Редактирования группы',
                                           form=form, message='В группе нет ни одного модуля',
                                           item=group)
                group.title = form.title.data
                # изменение списка пользователей:
                for user in group.users:  # удаление лишних
                    if user.id not in form.users.data:
                        group.users.remove(user)
                for user_id in form.users.data:  # добавление новых
                    user = session.query(User).filter(User.id == user_id).first()
                    if user not in group.users:
                        group.users.append(user)

                # изменение списка редакторов:
                for user in group.editors:  # удаление лишних
                    if user.id not in form.editors.data:
                        group.editors.remove(user)
                for user_id in form.editors.data:  # добавление новых
                    user = session.query(User).filter(User.id == user_id).first()
                    if user not in group.editors:
                        group.editors.append(user)

                # изменение списка модулей:
                for switch in group.switches:  # удаление старых
                    if switch.id not in form.switches.data:
                        group.switches.remove(switch)
                for switch_id in form.switches.data:  # добавление новых
                    switch = session.query(Switch).filter(Switch.id == switch_id).first()
                    if switch not in group.switches:
                        group.switches.append(switch)

                group.public_edit = not bool(group.editors)
                group.public_use = not bool(group.users)
                session.merge(group)
                session.commit()
                return redirect('/groups_list')
        else:
            abort(403)
    else:
        abort(404)


# обработчик удаления группы модулей
@app.route('/delete_group/<int:group_id>')
@login_required
def delete_group(group_id):
    session = db_session.create_session()
    group = session.query(Group).filter(Group.id == group_id).first()
    if group:  # проверка существования
        if current_user in group.editors or group.public_edit:  # проверка прав
            session.delete(group)
            session.commit()
            return redirect('/groups_list')
        else:
            abort(403)
    abort(404)


# обработчик изменения состояния группы модулей
@app.route('/set_group/<int:group_id>/<int:state>')
@login_required
def set_group(group_id, state):
    session = db_session.create_session()
    group = session.query(Group).filter(Group.id == group_id).first()
    if group:  # проверка существования
        if current_user in group.users or group.public_use:  # проверка прав
            for switch in group.switches:
                switch.status = state
                if switch.sid != 0:
                    sio.emit('get_msg', {'status': switch.status}, room=switch.sid)

                # отправка запроса об изменнии состояния на управляющее устройство
                # post(switch.house.web_hook, json={'port': switch.port, 'status': state})
            group.status = state
            session.merge(group)
            session.commit()
            return redirect('/groups_list')
        else:
            abort(403)
    else:
        abort(404)


# обработчик страницы регистрации пользователя
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    session = db_session.create_session()
    house_choices = [(house.id, house.title) for house in session.query(House).all()]
    # form.house_id.choices = house_choices
    if form.validate_on_submit():
        # проверка совпадения паролей
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация', form=form,
                                   message="Пароли не совпадают")
        # проверка уникальности почты
        session = db_session.create_session()
        if session.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='Регистрация', form=form,
                                   message="Такой пользователь уже есть")
        # проверка подлинности пароля от дома
        elif not session.query(House).filter(
                House.id == form.house_id.data).first().check_password(form.house_password.data):
            return render_template('register.html', title='Регистрация', form=form,
                                   message="Пароль от дома укзан неверно")
        user = User(name=form.name.data, email=form.email.data, house_id=form.house_id.data)
        user.set_password(form.password.data)
        session.add(user)
        session.commit()
        return redirect('/login')
    return render_template('register.html', title='Регистрация', form=form)


# обработчик страницы авторизации пользователя
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


# обработчик выхода из учётной записи
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


# обработчик запросов от Алисы
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


def get_device_id(environ):
    return environ.get('HTTP_DEVICE_ID', None)

#  Соединение с модулем умного дома
@sio.event
def connect(sid, environ):
    session = db_session.create_session()
    device_id = get_device_id(environ) or sid
    sio.save_session(sid, {'device_id': device_id})
    switch = session.query(Switch).filter(Switch.personal_name == device_id).first()
    switch.sid = sid
    print('{} is connected'.format(device_id))
    session.commit()

#  Отправка данных на модуль
@sio.event
def my_message(sid, data):
    # session = sio.get_session(sid)
    # print('Received data from {}: {}'.format(session['device_id'], data))
    sio.emit('get_msg', {'data': 'foobar'}, room=sid)

#  Разъединение с модулем умного дома
@sio.event
def disconnect(sid):
    session = db_session.create_session()
    switch = session.query(Switch).filter(Switch.sid == sid).first()
    if switch:
        switch.sid = 0
        print(switch.personal_name, 'is disconnected')
    session.commit()


if __name__ == '__main__':
    app.run()  # /host='192.168.1.222'/#
