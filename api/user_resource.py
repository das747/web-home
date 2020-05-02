from flask import jsonify
from flask_restful import Resource, reqparse, abort
from data import db_session
from data.users import User
from api.api_auth import house_auth, user_auth

parser = reqparse.RequestParser()
parser.add_argument('email', required=True)
parser.add_argument('password', required=True)
parser.add_argument('name', required=True)


class UserResource(Resource):
    @user_auth.login_required
    def get(self, user_id):
        session = db_session.create_session()
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            if user.id == user_auth.current_user().id:
                return jsonify({'user': user.to_dict(only=('id', 'name', 'email', 'house_id'))})
            else:
                abort(403)
        else:
            abort(404)

    @user_auth.login_required
    def put(self, user_id):
        session = db_session.create_session()
        args = parser.parse_args()
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            if user.id == user_auth.current_user().id:
                if session.query(User).filter(User.email == args['email'],
                                              User.id != user.id).first():
                    abort(422, message='Такой пользователь уже есть')
                user.name = args['name']
                user.email = args['email']
                user.set_password(args['password'])
                session.commit()
                return jsonify({'success': 'OK'})
            else:
                abort(403)
        else:
            abort(404)

    @user_auth.login_required
    def delete(self, user_id):
        session = db_session.create_session()
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            if user.id == user_auth.current_user().id:
                session.delete(user)
                session.commit()
                return jsonify({'success': 'OK'})
            else:
                abort(403)
        else:
            abort(404)


class UserListResource(Resource):
    @house_auth.login_required
    def post(self):
        args = parser.parse_args()
        session = db_session.create_session()
        if session.query(User).filter(User.email == args['email']).first():
            abort(422, message='Такой пользователь уже есть')
        user = User(name=args['name'], email=args['email'], house_id=house_auth.current_user().id)
        user.set_password(args['password'])
        session.add(user)
        session.commit()
        return jsonify({'success': 'OK'})

    @house_auth.login_required
    def get(self):
        session = db_session.create_session()
        users = session.query(User).filter(User.house_id == house_auth.current_user().id).all()
        return jsonify({'users': [user.to_dict(only=('id', 'name')) for user in users]})
