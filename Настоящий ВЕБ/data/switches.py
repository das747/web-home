import sqlalchemy
from sqlalchemy import orm

from .db_session import SqlAlchemyBase


class Switch(SqlAlchemyBase):
    __tablename__ = 'switches'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    title = sqlalchemy.Column(sqlalchemy.String)
    port = sqlalchemy.Column(sqlalchemy.Integer)
    status = sqlalchemy.Column(sqlalchemy.Boolean)
    house_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey('houses.id'))
    public_edit = sqlalchemy.Column(sqlalchemy.Boolean)
    public_use = sqlalchemy.Column(sqlalchemy.Boolean)
    groups = orm.relationship('Group', secondary='switches_to_groups', back_populates='switches')
    users = orm.relationship('User', secondary='users_to_switches', back_populates='usable_switches')
    editors = orm.relationship('User', secondary='editors_to_switches',
                               back_populates='editable_switches')
    house = orm.relation('House')

