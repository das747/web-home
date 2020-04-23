import sqlalchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .db_session import SqlAlchemyBase
from sqlalchemy import orm

users_to_switches = sqlalchemy.Table('users_to_switches', SqlAlchemyBase.metadata,
                                     sqlalchemy.Column('user', sqlalchemy.Integer,
                                                       sqlalchemy.ForeignKey('users.id')),
                                     sqlalchemy.Column('switch', sqlalchemy.Integer,
                                                       sqlalchemy.ForeignKey('switches.id')))

editors_to_switches = sqlalchemy.Table('editors_to_switches', SqlAlchemyBase.metadata,
                                       sqlalchemy.Column('user', sqlalchemy.Integer,
                                                         sqlalchemy.ForeignKey('users.id')),
                                       sqlalchemy.Column('switch', sqlalchemy.Integer,
                                                         sqlalchemy.ForeignKey('switches.id')))

users_to_groups = sqlalchemy.Table('users_to_groups', SqlAlchemyBase.metadata,
                                   sqlalchemy.Column('user', sqlalchemy.Integer,
                                                     sqlalchemy.ForeignKey('users.id')),
                                   sqlalchemy.Column('group', sqlalchemy.Integer,
                                                     sqlalchemy.ForeignKey('groups.id')))

editors_to_groups = sqlalchemy.Table('editors_to_groups', SqlAlchemyBase.metadata,
                                     sqlalchemy.Column('user', sqlalchemy.Integer,
                                                       sqlalchemy.ForeignKey('users.id')),
                                     sqlalchemy.Column('group', sqlalchemy.Integer,
                                                       sqlalchemy.ForeignKey('groups.id')))


class User(SqlAlchemyBase, UserMixin):
    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    email = sqlalchemy.Column(sqlalchemy.String)
    hashed_password = sqlalchemy.Column(sqlalchemy.String)
    house_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('houses.id'))
    usable_switches = orm.relationship("Switch", secondary='users_to_switches',
                                       back_populates='users')
    editable_switches = orm.relationship("Switch", secondary='editors_to_switches',
                                         back_populates='editors')
    usable_groups = orm.relationship('Group', secondary='users_to_groups', back_populates='users')
    editable_groups = orm.relationship('Group', secondary='editors_to_groups',
                                       back_populates='editors')
    house = orm.relation('House')

    def set_password(self, password):
        self.hashed_password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.hashed_password, password)
