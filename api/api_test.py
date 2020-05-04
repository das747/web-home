from requests import get, put, post, delete
from flask import jsonify
from requests.auth import HTTPBasicAuth


# для тестирования нужно подключить приложение к db/test.db

# класс с универсальными методами тестирования ресурсов
class BaseTest:
    url = 'http://localhost:5000/api/'
    args = {'old': {},  # аргументы создания объекта
            'new': {},  # аргументы редактирования объета
            'auth': {},  # данные для аутентификации
            'new_auth': {},  # обновлённые данные для аутентификации
            'parent': {},  # данные для аутентификации при создании объекта
            'type': '',  # название ресурса
            'checkfields': []}  # поля для проверки
    id = 2

    # создание объекта
    def test_post(self):
        resp = post(self.url, json=self.args['old'], auth=HTTPBasicAuth(**self.args['parent']))
        assert resp.status_code == 200

    # повторное создание объекта
    def test_same_post(self):
        resp = post(self.url, json=self.args['old'], auth=HTTPBasicAuth(**self.args['parent']))
        assert resp.status_code == 422

    # получение списка всех объектов
    def test_get_list(self):
        resp = get(self.url, auth=HTTPBasicAuth(**self.args['parent']))
        assert resp.status_code == 200

    # получение данных объекта без аутентификации
    def test_get_unauth(self):
        resp = get(self.url + f'/{self.id}')
        assert resp.status_code == 401

    # получение данных объекта с неверными параметрами аутентификации
    def test_get_wrong_auth(self):
        resp = get(self.url + f'/{self.id}',
                   auth=HTTPBasicAuth('', ''))
        assert resp.status_code == 401

    # неавторизирванное получение данных объекта
    def test_get_forbidden(self):
        resp = get(self.url + f'/1', auth=HTTPBasicAuth(**self.args['auth']))
        assert resp.status_code == 403

    # получение данных несуществующего объекта
    def test_get_not_found(self):
        resp = get(self.url + f'/9999', auth=HTTPBasicAuth(**self.args['auth']))
        assert resp.status_code == 404

    # получение данных объекта
    def test_get_one(self):
        resp = get(self.url + f'/{self.id}', auth=HTTPBasicAuth(**self.args['auth']))
        assert resp.status_code == 200
        data = resp.json()[self.args['type']]
        for arg in self.args['checkfields']:
            assert data[arg] == self.args['old'][arg]

    # редактирование объета без аутентификации
    def test_put_unauth(self):
        resp = put(self.url + f'/{self.id}', json=self.args['new'])
        assert resp.status_code == 401

    # редактирование объекта с неверными параметрами аутентификации
    def test_put_wrong_auth(self):
        resp = put(self.url + f'/{self.id}',
                   json=self.args['new'],
                   auth=HTTPBasicAuth('', ''))
        assert resp.status_code == 401

    # неавторизированное редактирование объекта
    def test_put_forbidden(self):
        resp = put(self.url + f'/1',
                   json=self.args['new'],
                   auth=HTTPBasicAuth(**self.args['auth']))
        assert resp.status_code == 403

    # редактирование несуществующего объекта
    def test_put_not_found(self):
        resp = put(self.url + f'/9999',
                   json=self.args['new'],
                   auth=HTTPBasicAuth(**self.args['auth']))
        assert resp.status_code == 404

    # редактирование объекта
    def test_put(self):
        resp = put(self.url + f'/{self.id}',
                   json=self.args['new'],
                   auth=HTTPBasicAuth(**self.args['auth']))
        assert resp.status_code == 200
        data = get(self.url + f'/{self.id}',
                   auth=HTTPBasicAuth(**self.args['new_auth'])).json()[self.args['type']]
        for arg in self.args['checkfields']:
            assert data[arg] == self.args['new'][arg]

    # удаление объекта без аутентификации
    def test_delete_unauth(self):
        resp = delete(self.url + f'/{self.id}')
        assert resp.status_code == 401

    # удаление объекта с неверными параметрами аутентификации
    def test_delete_wrong_auth(self):
        resp = delete(self.url + f'/{self.id}',
                      auth=HTTPBasicAuth('', ''))
        assert resp.status_code == 401

    # неавторизированное удалени объекта
    def test_delete_forbidden(self):
        resp = delete(self.url + f'/1', auth=HTTPBasicAuth(**self.args['new_auth']))
        assert resp.status_code == 403

    # удаление несуществующего объекта
    def test_delete_not_found(self):
        resp = delete(self.url + f'/9999', auth=HTTPBasicAuth(**self.args['new_auth']))
        assert resp.status_code == 404

    # удаление объекта
    def test_delete_one(self):
        resp = delete(self.url + f'/{self.id}', auth=HTTPBasicAuth(**self.args['new_auth']))
        assert resp.status_code == 200
        r = get(self.url + f'/{self.id}', auth=HTTPBasicAuth(**self.args['new_auth']))
        assert r.status_code == 401 or r.status_code == 404


# класс тестов api домов
class TestHouse(BaseTest):
    url = BaseTest.url + 'house'
    args = {'old': {'title': 'old_house', 'web_hook': 'old_hook', 'password': 'password'},
            'new': {'title': 'new_house', 'web_hook': 'new_hook', 'password': 'newpass'},
            'auth': {'username': 'old_house', 'password': 'password'},
            'new_auth': {'username': 'new_house', 'password': 'newpass'},
            'parent': {'username': '', 'password': ''},
            'type': 'house',
            'checkfields': ['title', 'web_hook']}


# класс тестов api пользователей
class TestUser(BaseTest):
    url = BaseTest.url + 'user'
    args = {'old': {'name': 'old_user', 'email': 'old_email', 'password': 'password'},
            'new': {'name': 'new_user', 'email': 'new_email', 'password': 'newword'},
            'auth': {'username': 'old_email', 'password': 'password'},
            'new_auth': {'username': 'new_email', 'password': 'newword'},
            'parent': {'username': 'test', 'password': 'pass'},
            'type': 'user',
            'checkfields': ['name', 'email']}
    id = 3


# класс тестов api модулей
class TestSwitch(BaseTest):
    url = BaseTest.url + 'switch'
    args = {'old': {'title': 'old_module', 'port': 8000, 'status': 0,
                    'public_use': 0, 'public_edit': 1},
            'new': {'title': 'new_module', 'port': 8000, 'status': 1,
                    'public_use': 1, 'public_edit': 0},
            'auth': {'username': 'test@smart.house', 'password': '12345678'},
            'type': 'switch'}
    args['parent'] = args['auth']
    args['new_auth'] = args['auth']
    args['checkfields'] = args['old'].keys()
    id = 4


# класс тестов api групп модулей
class TestGroup(BaseTest):
    url = BaseTest.url + 'group'
    args = {'old': {'title': 'old_group', 'switches': [2, 3], 'status': 0,
                    'public_use': 0, 'public_edit': 1},
            'new': {'title': 'new_group', 'switches': [2, 3], 'status': 1,
                    'public_use': 1, 'public_edit': 0},
            'auth': {'username': 'test@smart.house', 'password': '12345678'},
            'type': 'group'}
    args['parent'] = args['auth']
    args['new_auth'] = args['auth']
    args['checkfields'] = args['old'].keys()
