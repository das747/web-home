from flask import jsonify
from flask_restful import Resource, reqparse, abort
from data import db_session
from data.users import User
from data.groups import Group
from data.switches import Switch
from api.api_auth import user_auth

parser = reqparse.RequestParser()
parser.add_argument('title', required=True, )
parser.add_argument('switches', required=True, action='append', type=int)
parser.add_argument('status', required=True, type=bool)
parser.add_argument('public_use', required=True, type=bool)
parser.add_argument('public_edit', required=True, type=bool)


class GroupResource(Resource):
    @user_auth.login_required
    def get(self, group_id):
        session = db_session.create_session()
        group = session.query(Group).filter(Group.id == group_id).first()
        user = session.query(User).filter(User.id == user_auth.current_user().id).first()
        if group:
            if (user in group.users or user in group.editors
                    or group.public_edit or group.public_use):
                res = group.to_dict(rules=('-users', '-editors', '-switches', '-house'))
                res['switches'] = [switch.id for switch in group.switches]
                return jsonify({'group': res})
            else:
                abort(403)
        else:
            abort(404)

    @user_auth.login_required
    def put(self, group_id):
        session = db_session.create_session()
        group = session.query(Group).filter(Group.id == group_id).first()
        user = session.query(User).filter(User.id == user_auth.current_user().id).first()
        if group:
            if user in group.editors or group.public_edit:
                args = parser.parse_args()
                if session.query(Group).filter(Group.title == args['title'],
                                               Group.id != group.id,
                                               Group.house_id == group.house_id).first():
                    abort(422, message='Имя группы уже занято')
                elif not args['switches']:
                    abort(422, message='В группе нет ни одного модуля')
                group.title = args['title']
                for switch in group.switches:
                    if switch.id not in args['switches']:
                        group.switches.remove(switch)
                for switch_id in args['switches']:
                    switch = session.query(Switch).filter(Switch.id == switch_id).first()
                    if switch not in group.switches:
                        group.switches.append(switch)

                if group.status != args['status']:
                    group.status = args['status']
                    for switch in group.switches:
                        switch.status = args['status']
                        # post(switch.house.web_hook,
                        # json={'port': switch.port, 'status': args['status']})

                if args['public_use']:
                    group.users.clear()
                elif user not in group.users:
                    group.user.append(user)
                group.public_use = args['public_use']

                if args['public_edit']:
                    group.editors.clear()
                elif user not in group.editors:
                    group.editors.append(user)
                group.public_edit = args['public_edit']

                session.merge(group)
                session.commit()

                return jsonify({'success': 'OK'})
            else:
                abort(403)
        else:
            abort(404)

    @user_auth.login_required
    def delete(self, group_id):
        session = db_session.create_session()
        group = session.query(Group).filter(Group.id == group_id).first()
        if group:
            if user_auth.current_user() in group.editors:
                session.delete(group)
                session.commit()
                return jsonify({'success': 'OK'})
            else:
                abort(403)
        else:
            abort(404)


class GroupListResource(Resource):
    @user_auth.login_required
    def post(self):
        args = parser.parse_args()
        session = db_session.create_session()
        user = session.query(User).filter(User.id == user_auth.current_user().id).first()
        if session.query(Group).filter(Group.title == args['title'],
                                       Group.house_id == user.house_id).first():
            abort(422, message='Имя модуля уже занято')
        elif not args['switches']:
            abort(422, message='В группе нет ни одного модуля')

        group = Group(title=args['title'], status=args['status'],
                      house_id=user.house_id)
        session.add(group)

        for switch_id in args['switches']:
            group.switches.append(session.query(Switch).filter(Switch.id == switch_id).first())

        for switch in group.switches:
            switch.status = args['status']
            # post(switch.house.web_hook, json={'port': switch.port, 'status': args['status']})

        if not args['public_use']:
            group.users.append(user)
        group.public_use = args['public_use']

        if not args['public_edit']:
            group.editors.append(user)
        group.public_edit = args['public_edit']

        session.merge(group)
        session.commit()
        return jsonify({'success': 'OK'})

    @user_auth.login_required
    def get(self):
        user = user_auth.current_user()
        return jsonify({
            'groups': [group.to_dict(only=('id', 'title', 'public_use', 'public_edit')) for group
                       in user.usable_groups + user.editable_groups]})
