from flask_httpauth import HTTPBasicAuth
from data import db_session
from data.users import *
from data.houses import *

user_auth = HTTPBasicAuth()
house_auth = HTTPBasicAuth()


@user_auth.verify_password
def check_user_password(username, password):
    session = db_session.create_session()
    user = session.query(User).filter(User.email == username).first()
    if user and user.check_password(password):
        return user


@house_auth.verify_password
def check_house_password(username, password):
    session = db_session.create_session()
    house = session.query(House).filter(House.title == username).first()
    if house and house.check_password(password):
        return house
