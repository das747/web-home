from collections import defaultdict

from requests import post
from flask import Flask, request, render_template
import logging
import json
import os

from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from flask_wtf import FlaskForm
from werkzeug.utils import redirect
from wtforms import (PasswordField, SubmitField, BooleanField, StringField, SelectMultipleField,
                     widgets, IntegerField, SelectField)
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired

import autodeploy
import house_resource
from flask_restful import Api, abort
from data import db_session
from data.switches import *
from data.users import *
from data.groups import *
from data.houses import *

app = Flask(__name__)
logging.basicConfig(level=logging.INFO,
                    format='%(filename)s --> %(levelname)s: %(message)s')
api = Api(app)
app.register_blueprint(autodeploy.blueprint)
# api.add_resource(house_resource.HouseResource, '/api/v2/func/<device_id>/<int:status>')


sessionStorage = defaultdict(lambda: None)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'
login_manager = LoginManager()
login_manager.init_app(app)

if not os.access('./db', os.F_OK):
    os.mkdir('./db')
db_session.global_init("db/smart_house.db")


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
    submit = SubmitField('Сохранить')


class HouseEditForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired()])
    address = StringField('WebHook адрес', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class GroupForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired()])
    switches = MultiCheckboxField('Выбор модулей', coerce=int)
    users = MultiCheckboxField('Кто может использовать (если не выбрать доступно всем)', coerce=int)
    editors = MultiCheckboxField('Кто может редактировать (если не выбрать доступно всем)',
                                 coerce=int)
    submit = SubmitField('Сохранить')


class HouseRegisterForm(FlaskForm):
    title = StringField('Название', validators=[DataRequired()])
    address = StringField('WebHook адрес', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    password_again = PasswordField('Повторите пароль', validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class RegisterForm(FlaskForm):
    email = EmailField('Почта', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    password_again = PasswordField('Повторите пароль', validators=[DataRequired()])
    name = StringField('Имя пользователя', validators=[DataRequired()])
    house_id = SelectField('Дом', coerce=int)
    house_password = PasswordField('Пароль от дома', validators=[DataRequired()])
    submit = SubmitField('Регистрация')

class UserEditForm(FlaskForm):
    email = StringField('Почта', validators=[DataRequired()])
    name = StringField('Имя', validators=[DataRequired()])
    password = StringField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Сохранить')
    
def handle_dialog(res, req):
    session = db_session.create_session()
    user_id = req['session']['user_id']
    if req['session']['new']:
        sessionStorage[user_id] = {'log_in': False, 'user': None}
        res['response']['text'] = 'Привет, я помощник для умного дома'
        return
    res['response']['text'] = 'Nothing'
    res['response']['buttons'] = []
    if req['request']['command'].lower() in ['помощь', 'что ты умеешь']:
        res['response']['text'] = 'Я навык, который поможет вам в управлении умным домом.' \
                                  'Я могу включить и выключать модули умного дома, ' \
                                  'сообщать вам информацию о их состоянии. ' \
                                  'Для начала работы, вам необходимо зарегистрироваться на сайте ' \
                                  'http://84.201.144.114/register'
        return
    if not sessionStorage[user_id]['log_in']:
        res['response']['text'] = 'Я не могу вам помочь, пока вы не войдете,' \
                                  'чтобы войти, введите свой email и пароль(через пробел)'
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

    if req['request']['command'].lower() == 'выйти':
        res['response']['text'] = 'Вы вышли'
        sessionStorage[user_id]['user'] = None
        sessionStorage[user_id]['log_in'] = False
        res['response']['buttons'] = []
        return

    if req['request']['command'].lower() == 'help':
        res['response']['text'] = '''Включить <Название модуля>
            Выключить <Название модуля>
            Включить группу <Название группы>
            Выключить группу <Название группы>
            Состояние модулей(список модулей и их состояние)'''
        return

    if 'состояние модулей' in req['request']['command'].lower():
        res['response']['text'] = ''
        user = sessionStorage[user_id]['user']
        if user.usable_swithes == []:
            res['response']['text'] = 'У вас нет модулей умного дома'
        for switch in user.usable_switches:
            module = session.query(Switch).filter(Switch.id == switch.id).first()
            res['response']['text'] += str(
                module.title) + ': ' + 'включен' * module.status + 'выключен' * (
                                               1 - module.status) + '\n'
        return

    if 'включить' in req['request']['command'].lower():
        session = db_session.create_session()
        pos = req['request']['command'].lower().find('включить')
        target = req['request']['command'][pos + 9:].lower().strip()
        print(target)
        if target:
            user = sessionStorage[user_id]['user']
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

            else:

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

    elif 'выключить' in req['request']['command'].lower():
        session = db_session.create_session()
        pos = req['request']['command'].lower().find('выключить')
        target = req['request']['command'][pos + 10:].lower().strip()
        print(target)
        if target:
            res['response']['text'] = 'Не смогла найти'
            user = sessionStorage[user_id]['user']
            if len(target.split()) > 1 and target.split()[0] == 'группу':
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
                    else:
                        res['response']['text'] = 'Я не смогла найти такую группу, возможно вы ввели' \
                                                  ' неправильное название группы,' \
                                                  ' или вы не можете ей управлять'
            else:
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


@app.route("/", methods=['GET'])
def start():
    session = db_session.create_session()
    if current_user.is_authenticated:
        user = session.query(User).filter(User.id == current_user.id).first()
        public = session.query(Switch).filter((Switch.public_edit == 1) |
                                              (Switch.public_use == 1),
                                              Switch.house_id == user.house_id).all()
        switches = sorted({*user.usable_switches, *user.editable_switches, *public},
                          key=lambda s: s.id)
    else:
        switches = []
    return render_template('index.html', title='Smart house', items=switches, type='switch')
  

  
@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    form = UserEditForm()
    session = db_session.create_session()
    user = session.query(User).get(user_id)
    if request.method == 'GET':

        form.name.data = user.name
        form.email.data = user.email
        return render_template('user.html', title='Редактирование пользователя', form=form, item=user)
    elif form.validate_on_submit():
        session = db_session.create_session()
        user = session.query(User).get(user_id)
        form.name.data = user.name
        form.email.data = user.email

        if session.query(User).filter(User.email == form.email.data, User.id != user_id).first():
            return render_template('user.html', title='Редактирование пользователя', form=form,
                                   message="Такая почта уже зарегистрирована", item=user)
        elif form.password.data != form.password_again.data:
            return render_template('user.html', form=form, title='Редактирование пользователя',
                                   message='Пароли не совпадают', item=user)

        user.name = form.name.data
        user.email = form.email.data
        session.commit()
        return redirect('/')
    return render_template('user.html', title='Редактирование пользователя', form=form, item=user)


@app.route('/delete_user/<int:user_id>', methods=['GET'])
@login_required
def delete_user(user_id):
    session = db_session.create_session()
    user = session.query(User).get(user_id)
    if user:
        if current_user.is_authenticated and current_user.id == user.id:
            logout_user()
            session.delete(user)
            session.commit()
            return redirect('/')
        else:
            abort(403)
    else:
        abort(404)
  

@app.route('/add_switch', methods=['GET', 'POST'])
@login_required
def add_switch():
    form = SwitchForm()
    session = db_session.create_session()
    all_users = [(user.id, user.name) for user in
                 session.query(User).filter(User.house_id == current_user.house_id).all()]
    form.users.choices = all_users
    form.editors.choices = all_users
    if form.validate_on_submit():
        if session.query(Switch).filter(Switch.title == form.title.data,
                                        Switch.house_id == current_user.house_id).first():
            return render_template('switch.html', title='Добавление модуля', form=form,
                                   message='Имя модуля уже занято')
        elif session.query(Switch).filter(Switch.port == form.port.data,
                                          Switch.house_id == current_user.house_id).first():
            return render_template('switch.html', title='Добавление модуля', form=form,
                                   message='Этот порт уже используется')

        switch = Switch(title=form.title.data.lower(), status=0, port=form.port.data,
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


@app.route('/edit_switch/<int:switch_id>', methods=['GET', 'POST'])
@login_required
def edit_switch(switch_id):
    form = SwitchForm()
    session = db_session.create_session()
    all_users = [(user.id, user.name) for user in
                 session.query(User).filter(User.house_id == current_user.house_id).all()]
    form.editors.choices = all_users
    form.users.choices = all_users
    switch = session.query(Switch).filter(Switch.id == switch_id).first()
    if switch:
        if current_user in switch.editors or switch.public_edit:
            if request.method == 'GET':
                form.title.data = switch.title
                form.port.data = switch.port
                form.editors.data = [user.id for user in switch.editors]
                form.users.data = [user.id for user in switch.users]
                return render_template('switch.html', title='Редактирование модуля', form=form, item=switch)

            elif form.validate_on_submit():
                if session.query(Switch).filter(Switch.title == form.title.data,
                                                Switch.id != switch_id,
                                                Switch.house_id == switch.house_id).first():
                    return render_template('switch.html', title='Редактирования модуля',
                                           form=form, message='Имя модуля уже занято', item=switch)
                elif session.query(Switch).filter(Switch.port == form.port.data,
                                                  Switch.id != switch_id,
                                                  Switch.house_id == switch.house_id).first():
                    return render_template('switch.html', title='Редактирования модуля',
                                           form=form, message='"Этот порт уже используется"', item=switch)
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


@app.route('/delete_switch/<int:switch_id>', methods=['GET'])
@login_required
def delete_switch(switch_id):
    session = db_session.create_session()
    switch = session.query(Switch).filter(Switch.id == switch_id).first()
    if switch:
        if switch.public_edit or current_user in switch.editors:
            session.delete(switch)
            session.commit()
            return redirect('/')
        else:
            abort(403)
    else:
        abort(404)


@app.route('/set_switch/<int:device_id>/<int:state>', methods=['GET', 'POST'])
@login_required
def turn_light(device_id, state):
    session = db_session.create_session()
    user = session.query(User).filter(User.id == current_user.id).first()
    switch = session.query(Switch).filter(Switch.id == device_id).first()
    if switch:
        if switch.public_use or user in switch.users:
            switch.status = state
            if not state:
                for group in switch.groups:
                    group.status = state
            session.commit()
        #     post(switch.house.web_hook, json={'port': switch.port, 'status': switch.status})
        else:
            abort(403)
    else:
        abort(404)
    return redirect('/')


@app.route('/add_house', methods=['GET', 'POST'])
def add_house():
    form = HouseRegisterForm()
    if form.validate_on_submit():
        session = db_session.create_session()
        if session.query(House).filter(House.title == form.title.data).first():
            return render_template('house.html', form=form, title='Добавление дома',
                                   message='Имя дома уже занято')
        elif session.query(House).filter(House.web_hook == form.address.data).first():
            return render_template('house.html', form=form, title='Добавление дома',
                                   message='Дом с таким адресом уже добавлен')
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


@app.route('/edit_house/<int:house_id>', methods=['GET', 'POST'])
@login_required
def edit_house(house_id):
    form = HouseEditForm()
    session = db_session.create_session()
    house = session.query(House).filter(House.id == house_id).first()
    user = session.query(User).filter(User.id == current_user.id).first()
    if house:
        if house.id == user.house.id:
            if request.method == 'GET':
                form.address.data = house.web_hook
                form.title.data = house.title
                return render_template('house.html', title='Редактирование дома', form=form)
            elif form.validate_on_submit():
                if session.query(House).filter(House.title == form.title.data,
                                               House.id != house_id).first():
                    return render_template('house.html', title='Редактирование дома', form=form,
                                           message='Имя дома уже занято')
                elif session.query(House).filter(House.web_hook == form.address.data,
                                                 House.id != house_id).first():
                    return render_template('house.html', title='Редактирование дома', form=form,
                                           message='Дом с таким адресом уже существует')
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


@app.route('/groups_list')
def list_groups():
    session = db_session.create_session()
    if current_user.is_authenticated:
        user = session.query(User).filter(User.id == current_user.id).first()
        public = session.query(Group).filter((Group.public_edit == 1) |
                                             (Group.public_use == 1),
                                             Group.house_id == user.house_id).all()
        groups = sorted({*user.usable_groups, *user.editable_groups, *public},
                        key=lambda s: s.id)
    else:
        groups = []
    return render_template('index.html', title='Smart house', items=groups, type='group')


@app.route('/add_group', methods=['GET', 'POST'])
@login_required
def add_group():
    session = db_session.create_session()
    user = session.query(User).filter(User.id == current_user.id).first()
    form = GroupForm()
    house_users = [(user.id, user.name) for user in
                   session.query(User).filter(User.house_id == user.house_id).all()]
    form.users.choices = house_users
    form.editors.choices = house_users
    usable_switches = user.usable_switches + session.query(Switch).filter(Switch.public_use == 1,
                                                                          Switch.house_id == user.house_id).all()
    form.switches.choices = [(s.id, s.title) for s in usable_switches]
    if form.validate_on_submit():
        if session.query(Group).filter(Group.title == form.title.data,
                                       Group.house_id == user.house_id).first():
            return render_template('group.html', title='Добавление группы', form=form,
                                   message='Имя группы уже занято')
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


@app.route('/edit_group/<int:group_id>', methods=['GET', 'POST'])
@login_required
def edit_group(group_id):
    form = GroupForm()
    session = db_session.create_session()
    user = session.query(User).filter(User.id == current_user.id).first()
    all_users = [(user.id, user.name) for user in
                 session.query(User).filter(User.house_id == current_user.house_id).all()]
    form.editors.choices = all_users
    form.users.choices = all_users
    usable_switches = user.usable_switches + session.query(Switch).filter(Switch.public_use == 1,
                                                                          Switch.house_id == user.house_id).all()
    form.switches.choices = [(s.id, s.title) for s in usable_switches]
    group = session.query(Group).filter(Group.id == group_id).first()
    if group:
        if current_user in group.editors or group.public_edit:
            if request.method == 'GET':
                form.title.data = group.title
                form.editors.data = [user.id for user in group.editors]
                form.users.data = [user.id for user in group.users]
                form.switches.data = [switch.id for switch in group.switches]
                return render_template('group.html', title='Редактирование группы', form=form, item=group)

            elif form.validate_on_submit():
                if session.query(Group).filter(Group.title == form.title.data,
                                               Group.id != group_id,
                                               Group.house_id == group.house_id).first():
                    return render_template('group.html', title='Редактирования группы',
                                           form=form, message='Имя группы уже занято', item=group)
                elif not form.switches.data:
                    return render_template('group.html', title='Редактирования группы',
                                           form=form, message='В группе нет ни одного модуля', item=group)
                group.title = form.title.data
                for user in group.users:
                    if user.id not in form.users.data:
                        group.users.remove(user)
                for user_id in form.users.data:
                    user = session.query(User).filter(User.id == user_id).first()
                    if user not in group.users:
                        group.users.append(user)
                for user in group.editors:
                    if user.id not in form.editors.data:
                        group.editors.remove(user)
                for user_id in form.editors.data:
                    user = session.query(User).filter(User.id == user_id).first()
                    if user not in group.editors:
                        group.editors.append(user)
                for switch in group.switches:
                    if switch.id not in form.switches.data:
                        group.switches.remove(switch)
                for switch_id in form.switches.data:
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


@app.route('/delete_group/<int:group_id>')
@login_required
def delete_group(group_id):
    session = db_session.create_session()
    group = session.query(Group).filter(Group.id == group_id).first()
    if group:
        if current_user in group.editors or group.public_edit:
            session.delete(group)
            session.commit()
            return redirect('/groups_list')
        else:
            abort(403)
    abort(404)


@app.route('/set_group/<int:group_id>/<int:state>')
@login_required
def set_group(group_id, state):
    session = db_session.create_session()
    group = session.query(Group).filter(Group.id == group_id).first()
    if group:
        if current_user in group.users or group.public_use:
            for switch in group.switches:
                switch.status = state
            group.status = state
            session.merge(group)
            session.commit()
            #     post(switch.house.web_hook, json={'port': switch.port, 'status': switch.status})
            return redirect('/groups_list')
        else:
            abort(403)
    else:
        abort(404)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    session = db_session.create_session()
    house_choices = [(house.id, house.title) for house in session.query(House).all()]
    form.house_id.choices = house_choices
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация', form=form,
                                   message="Пароли не совпадают")
        session = db_session.create_session()
        if session.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='Регистрация', form=form,
                                   message="Такой пользователь уже есть")

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


if __name__ == '__main__':
    app.run()
