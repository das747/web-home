from flask import jsonify
from flask_restful import Resource, reqparse, abort
from data import db_session
from data.users import User
from data.switches import Switch
from api.api_auth import user_auth
from requests import post

parser = reqparse.RequestParser()
parser.add_argument('title', required=True, )
parser.add_argument('port', required=True, type=int)
parser.add_argument('status', required=True, type=bool)
parser.add_argument('public_use', required=True, type=bool)
parser.add_argument('public_edit', required=True, type=bool)


class SwitchResource(Resource):
    @user_auth.login_required
    def get(self, switch_id):
        session = db_session.create_session()
        switch = session.query(Switch).filter(Switch.id == switch_id).first()
        user = session.query(User).filter(User.id == user_auth.current_user().id).first()
        if switch:
            if (user in switch.users or user in switch.editors
                    or switch.public_edit or switch.public_use):
                return jsonify({'switch': switch.to_dict(only=(
                    'id', 'title', 'port', 'status', 'house_id', 'public_use', 'public_edit'))})
            else:
                abort(403)
        else:
            abort(404)

    @user_auth.login_required
    def put(self, switch_id):
        session = db_session.create_session()
        switch = session.query(Switch).filter(Switch.id == switch_id).first()
        user = session.query(User).filter(User.id == user_auth.current_user().id).first()
        if switch:
            if user in switch.editors or switch.public_edit:
                args = parser.parse_args()
                if session.query(Switch).filter(Switch.title == args['title'],
                                                Switch.id != switch.id,
                                                Switch.house_id == switch.house_id).first():
                    abort(422, message='Имя модуля уже занято')
                elif session.query(Switch).filter(Switch.port == args['port'],
                                                  Switch.id != switch.id,
                                                  Switch.house_id == switch.house_id).first():
                    abort(422, message='Этот порт уже используется')
                switch.title = args['title']
                switch.port = args['port']
                switch.status = args['status']
                if args['public_use']:
                    switch.users.clear()
                elif user not in switch.users:
                    switch.user.append(user)
                switch.public_use = args['public_use']

                if args['public_edit']:
                    switch.editors.clear()
                elif user not in switch.editors:
                    switch.editors.append(user)
                switch.public_edit = args['public_edit']

                session.merge(switch)
                session.commit()
                # post(switch.house.web_hook, json={'port': switch.port, 'status': switch.status})
                return jsonify({'success': 'OK'})
            else:
                abort(403)
        else:
            abort(404)

    @user_auth.login_required
    def delete(self, switch_id):
        session = db_session.create_session()
        switch = session.query(Switch).filter(Switch.id == switch_id).first()
        if switch:
            if user_auth.current_user() in switch.editors:
                session.delete(switch)
                session.commit()
                return jsonify({'success': 'OK'})
            else:
                abort(403)
        else:
            abort(404)


class SwitchListResource(Resource):
    @user_auth.login_required
    def post(self):
        args = parser.parse_args()
        session = db_session.create_session()
        user = session.query(User).filter(User.id == user_auth.current_user().id).first()
        if session.query(Switch).filter(Switch.title == args['title'],
                                        Switch.house_id == user.house_id).first():
            abort(422, message='Имя модуля уже занято')
        elif session.query(Switch).filter(Switch.port == args['port'],
                                          Switch.house_id == user.house_id).first():
            abort(422, message='Этот порт уже используется')
        switch = Switch(title=args['title'], port=args['port'], status=args['status'],
                        house_id=user.house_id)
        session.add(switch)
        if not args['public_use']:
            switch.users.append(user)
        switch.public_use = args['public_use']

        if not args['public_edit']:
            switch.editors.append(user)
        switch.public_edit = args['public_edit']
        session.merge(switch)
        session.commit()
        # post(switch.house.web_hook, json={'port': switch.port, 'status': switch.status})
        return jsonify({'success': 'OK'})

    @user_auth.login_required
    def get(self):
        user = user_auth.current_user()
        return jsonify({
            'switches': [switch.to_dict(only=('id', 'title', 'public_use', 'public_edit')) for switch
                         in user.usable_switches + user.editable_switches]})
