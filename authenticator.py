import MetaTrader5 as mt5

class MT5Auth:
    """Класс для авторизации в MetaTrader 5"""
    
    def __init__(self, account):
        self.account = account
        self.authorized = False
        self.initialize_connection()
    
    def initialize_connection(self):
        """Инициализация подключения к MT5"""
        if not mt5.initialize():
            error_msg = f"Ошибка инициализации MT5: {mt5.last_error()}"
            print(error_msg)
            raise ConnectionError(error_msg)
    
    def login(self):
        """Выполнение авторизации"""
        try:
            self.authorized = mt5.login(
                login=self.account["login"],
                password=self.account["password"],
                server=self.account["server"]
            )
            
            if self.authorized:
                print("Успешная авторизация в MT5")
            else:
                error_msg = f"Ошибка авторизации: {mt5.last_error()}"
                print(error_msg)
                
            return self.authorized
            
        except Exception as e:
            error_msg = f"Ошибка при авторизации: {str(e)}"
            print(error_msg)
    
    def logout(self):
        """Завершение сессии"""
        if self.authorized:
            mt5.shutdown()
            self.authorized = False
            print("Отключение от MT5 выполнено")
    
    def __del__(self):
        """Деструктор - автоматическое отключение при удалении объекта"""
        self.logout()

    def ensure_connection(self, max_retries: int = 3, wait_seconds: int = 2) -> bool:
        """Проверяет и при необходимости восстанавливает соединение с MT5.

        Возвращает True, если соединение установлено, иначе False.
        """
        import time

        retries = 0
        while retries < max_retries:
            try:
                # Попытка инициализации (если не инициализировано)
                initialized = mt5.initialize()
                if not initialized:
                    print("MT5 не инициализирован, пробуем инициализировать...")
                    try:
                        mt5.shutdown()
                    except Exception:
                        pass
                    time.sleep(1)
                    initialized = mt5.initialize()

                # Если терминал инициализирован, проверяем состояние терминала
                if initialized:
                    term = mt5.terminal_info()
                    if term is None:
                        # Если терминал не готов — попробуем выполнить вход
                        print("Терминал MT5 не отвечает, пытаемся выполнить login...")
                        logged = self.login()
                        if logged:
                            print("Успешная авторизация в MT5 (ensure_connection)")
                            return True
                        else:
                            print(f"Ошибка авторизации MT5: {mt5.last_error()}")
                    else:
                        # Терминал отвечает — считаем соединение установленным
                        print("MT5 инициализирован и терминал отвечает")
                        return True

                # Если не получилось — увеличиваем счётчик и ждём перед повторной попыткой
            except Exception as e:
                print(f"Ошибка при восстановлении соединения MT5: {e}")

            retries += 1
            print(f"Повторная попытка подключения MT5 ({retries}/{max_retries}) через {wait_seconds}s")
            time.sleep(wait_seconds)

        print("Не удалось восстановить соединение с MT5 после попыток")
        return False
