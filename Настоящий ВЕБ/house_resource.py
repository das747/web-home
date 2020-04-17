from flask import jsonify
from flask_restful import Resource, reqparse
from data import db_session
from data.house import *



class HouseResource(Resource):
    def get(self):
        session = db_session.create_session()
        house = session.query(Houses).get(1)
        # return jsonify({'light': house.light})
        return jsonify({'house': house.to_dict()})

    def post(self, device_id, status):
        session = db_session.create_session()
        house = session.query(Houses).get(device_id)
        house.status = status
        session.commit()
        return jsonify({'status': house.status, 'success': 'OK'})
