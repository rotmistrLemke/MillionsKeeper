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
