import unittest
import types
import sys
from types import SimpleNamespace

# Подготовка фейкового mt5 для тестирования
fake_mt5 = types.ModuleType('MetaTrader5')
state = {'inited': False, 'login_called': False}

fake_mt5.initialize = lambda: True
fake_mt5.shutdown = lambda: True
fake_mt5.terminal_info = lambda: SimpleNamespace(dummy=True)
fake_mt5.login = lambda **kwargs: True
fake_mt5.last_error = lambda: 'fake error'
fake_mt5.TIMEFRAME_H1 = 1

sys.modules['MetaTrader5'] = fake_mt5

import importlib
import authenticator
from authenticator import MT5Auth

class TestAuth(unittest.TestCase):
    def test_init_and_login_success(self):
        """Тест: MT5Auth создается и логин проходит успешно."""
        fake_mt5.initialize = lambda: True
        sys.modules['MetaTrader5'] = fake_mt5
        importlib.reload(authenticator)
        auth = authenticator.MT5Auth({'login': 123, 'password': 'x', 'server': 's'})
        result = auth.login()
        self.assertTrue(result)

    def test_init_fails_on_bad_initialize(self):
        """Тест: MT5Auth выбрасывает ошибку при неудачной инициализации."""
        fake_mt5.initialize = lambda: False
        sys.modules['MetaTrader5'] = fake_mt5
        importlib.reload(authenticator)
        with self.assertRaises(ConnectionError):
            authenticator.MT5Auth({'login': 1, 'password': 'x', 'server': 's'})

if __name__ == '__main__':
    unittest.main()
