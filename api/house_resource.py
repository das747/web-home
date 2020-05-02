from flask import jsonify
from flask_restful import Resource, reqparse, abort
from data import db_session
from data.houses import House
from api.api_auth import house_auth

parser = reqparse.RequestParser()
parser.add_argument('title', required=True)
parser.add_argument('web_hook', required=True)
parser.add_argument('password', required=True)


class HouseResource(Resource):
    @house_auth.login_required
    def get(self, house_id):
        session = db_session.create_session()
        house = session.query(House).filter(House.id == house_id).first()
        if house:
            if house_id == house_auth.current_user().id:
                return jsonify({'house': house.to_dict(only=('id', 'title', 'web_hook'))})
            else:
                abort(403)
        else:
            abort(404)

    @house_auth.login_required
    def put(self, house_id):
        session = db_session.create_session()
        house = session.query(House).filter(House.id == house_id).first()
        if house:
            if house_id == house_auth.current_user().id:
                args = parser.parse_args()
                if session.query(House).filter(House.title == args['title'], House.id != house_id).first():
                    abort(422, message=f'Имя дома {args["title"]} уже занято')
                elif session.query(House).filter(House.web_hook == args['web_hook'],
                                                 House.id != house_id).first():
                    abort(422, message=f'Дом с адресом {args["web_hook"]} уже добавлен')
                house.title = args['title']
                house.web_hook = args['web_hook']
                house.set_password(args['password'])
                session.commit()
                return jsonify({'success': 'OK'})
            else:
                abort(403)
        else:
            abort(404)

    @house_auth.login_required
    def delete(self, house_id):
        session = db_session.create_session()
        house = session.query(House).filter(House.id == house_id).first()
        if house:
            if house_auth.current_user().id == house_id:
                session.delete(house)
                session.commit()
                return jsonify({'success': 'OK'})
            else:
                abort(403)
        else:
            abort(404)


class HouseListResource(Resource):
    def post(self):
        args = parser.parse_args()
        session = db_session.create_session()
        if session.query(House).filter(House.title == args['title']).first():
            abort(422, message=f'Имя дома {args["title"]} уже занято')
        elif session.query(House).filter(House.web_hook == args['web_hook']).first():
            abort(422, message=f'Дом с адресом {args["web_hook"]} уже добавлен')
        house = House(title=args['title'], web_hook=args['web_hook'])
        house.set_password(args['password'])
        session.add(house)
        session.commit()
        return jsonify({'success': 'OK'})

    def get(self):
        session = db_session.create_session()
        houses = session.query(House).all()
        return jsonify({'houses': [item.to_dict(only=('id', 'title')) for item in houses]})


