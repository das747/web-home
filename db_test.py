from data.switches import *
from data.users import *
from data import db_session

db_session.global_init('db/house.sqlite')
session = db_session.create_session()
user = session.query(User).filter(User.id == 1).first()
user.rooms.clear()
print(user.rooms)
session.commit()