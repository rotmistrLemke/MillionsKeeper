import os
import MetaTrader5 as mt5


class MT5Auth:
    """Класс для авторизации в MetaTrader 5.

    На Windows Server, когда бот работает Windows-сервисом (LocalSystem),
    он не имеет доступа к терминалу MT5, запущенному в RDP-сессии под
    пользователем — у них разные IPC-каналы (-10004 No IPC connection).

    Решение: передаём `path` в `mt5.initialize()` — API запустит свою копию
    терминала в той же сессии, что и Python-процесс. Путь к терминалу
    задаётся через env MT5_PATH (например, C:\\Program Files\\MetaTrader 5\\terminal64.exe).
    Если переменной нет — используется дефолтное поведение initialize()
    без path (для разработки на локальной машине, где MT5 уже запущен).
    """

    def __init__(self, account):
        self.account = account
        self.authorized = False
        self.initialize_connection()

    def initialize_connection(self):
        """Инициализация подключения к MT5.

        При наличии MT5_PATH передаём логин/пароль/сервер прямо в initialize()
        — это и подключение, и авторизация одним вызовом. Гарантированно
        работает в служебной сессии Windows.
        """
        path = os.environ.get("MT5_PATH", "").strip()
        kwargs = {}
        if path:
            kwargs["path"] = path
        # Креды передаём ВСЕГДА, а не только вместе с path. Без них
        # initialize() подключается к тому счёту, который открыт в терминале,
        # — то есть к произвольному. Пустой login означает «подключиться к
        # текущей сессии терминала» и используется бэктест-утилитами.
        if self.account.get("login"):
            kwargs["login"]    = self.account["login"]
            kwargs["password"] = self.account["password"]
            kwargs["server"]   = self.account["server"]

        if not mt5.initialize(**kwargs):
            error_msg = f"Ошибка инициализации MT5: {mt5.last_error()}"
            print(error_msg)
            raise ConnectionError(error_msg)

        # Если креды передали в initialize — login() ниже всё равно
        # отработает (это no-op при уже активной сессии), полезно для логов.

    def _verify_account(self) -> None:
        """Сверяет фактически подключённый счёт с указанным в конфиге.

        Несовпадение означает торговлю чужим депозитом чужими параметрами —
        ошибка, которую нельзя ни залогировать и продолжить, ни повторить.
        """
        expected = self.account.get("login")
        if not expected:
            return  # подключение к текущей сессии терминала — сверять не с чем
        info = mt5.account_info()
        if info is None:
            raise ConnectionError(
                "Не удалось прочитать account_info — подключённый счёт "
                "не подтверждён. Торговля вслепую не начинается."
            )
        actual = getattr(info, "login", None)
        if actual != expected:
            raise ConnectionError(
                f"Подключён счёт {actual}, а в конфиге {expected}. "
                f"Проверьте MT5_LOGIN в .env и счёт, открытый в терминале."
            )

    def login(self):
        """Выполнение авторизации.

        Кидает ConnectionError, если подключение ушло не в тот счёт: вызов
        в main.py результат не проверяет, поэтому «вернуть False» здесь
        означало бы молча торговать чужим счётом.
        """
        try:
            # Если initialize уже залогинил — повторный login() это просто
            # подтверждение текущей сессии, безопасно.
            authorized = mt5.login(
                login=self.account["login"],
                password=self.account["password"],
                server=self.account["server"]
            )

            if not authorized:
                self.authorized = False
                print(f"Ошибка авторизации: {mt5.last_error()}")
                return False

            self._verify_account()
            self.authorized = True
            print(f"Успешная авторизация в MT5, счёт {self.account['login']}")
            return True

        except ConnectionError:
            self.authorized = False
            raise
        except Exception as e:
            self.authorized = False
            print(f"Ошибка при авторизации: {str(e)}")
            return False

    def reconnect(self) -> bool:
        """Повторная инициализация + логин (для ConnectionAgent). Не кидает; True при успехе."""
        try:
            self.initialize_connection()
            return bool(self.login())
        except Exception as e:
            print(f"MT5 reconnect failed: {e}")
            return False

    def logout(self):
        """Завершение сессии"""
        if self.authorized:
            mt5.shutdown()
            self.authorized = False
            print("Отключение от MT5 выполнено")
    
    def __del__(self):
        """Деструктор - автоматическое отключение при удалении объекта"""
        self.logout()
