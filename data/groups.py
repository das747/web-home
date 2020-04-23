import sqlalchemy
from sqlalchemy import orm

from .db_session import SqlAlchemyBase

switches_to_groups = sqlalchemy.Table('switches_to_groups', SqlAlchemyBase.metadata,
                                      sqlalchemy.Column('switch', sqlalchemy.Integer,
                                                        sqlalchemy.ForeignKey('switches.id')),
                                      sqlalchemy.Column('group', sqlalchemy.Integer,
                                                        sqlalchemy.ForeignKey('groups.id')))


class Group(SqlAlchemyBase):
    __tablename__ = 'groups'

    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    title = sqlalchemy.Column(sqlalchemy.String)
    public_edit = sqlalchemy.Column(sqlalchemy.Boolean)
    public_use = sqlalchemy.Column(sqlalchemy.Boolean)
    switches = orm.relationship('Switch', secondary='switches_to_groups', back_populates='groups')
    users = orm.relationship('User', secondary='users_to_groups', back_populates='usable_groups')
    editors = orm.relationship('User', secondary='editors_to_groups', back_populates='editable_groups')
