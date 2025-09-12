import MetaTrader5 as mt5
from datetime import datetime, timedelta

def get_closed_profit_period(date_from, date_to, symbol=None):
    """
    Получить сумму профита по завершенным сделкам за период
    """
    if not mt5.initialize():
        print("Ошибка подключения к MT5")
        return 0
    
    try:
        # Получаем историю сделок за указанный период
        deals = mt5.history_deals_get(date_from, date_to)
        
        if deals is None:
            print("Нет сделок за указанный период")
            return 0
        
        total_profit = 0.0
        closed_deals = []
        
        # Фильтруем только закрытые сделки и считаем профит
        for deal in deals:
            # Проверяем, что сделка закрывающая (тип 0 или 1) и по нужному символу
            if (deal.type in [0, 1] and  # 0 - buy, 1 - sell
                (symbol is None or deal.symbol == symbol)):
                total_profit += deal.profit
                closed_deals.append({
                    'ticket': deal.ticket,
                    'symbol': deal.symbol,
                    'type': 'BUY' if deal.type == 0 else 'SELL',
                    'profit': deal.profit,
                    'time': datetime.fromtimestamp(deal.time),
                    'volume': deal.volume
                })
        
        print(f"Найдено закрытых сделок: {len(closed_deals)}")
        print(f"Общий профит за период: {total_profit:.2f}")
        
        return total_profit, closed_deals
        
    except Exception as e:
        print(f"Ошибка при получении истории сделок: {e}")
        return 0, []
    finally:
        mt5.shutdown()

def get_profit_today(symbol=None):
    """Профит за сегодня"""
    date_from = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    date_to = datetime.now()
    return get_closed_profit_period(date_from, date_to, symbol)

def get_profit_this_week(symbol=None):
    """Профит за текущую неделю"""
    today = datetime.now()
    date_from = today - timedelta(days=today.weekday())
    #date_from = date_from.replace(hour=0, minute=0, second=0, microsecond=0)
    return get_closed_profit_period(date_from, today, symbol)

def get_profit_this_month(symbol=None):
    """Профит за текущий месяц"""
    today = datetime.now()
    date_from = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return get_closed_profit_period(date_from, today, symbol)

def get_profit_last_days(days, symbol=None):
    """Профит за последние N дней"""
    date_to = datetime.now()
    date_from = date_to - timedelta(days=days)
    date_from = date_from.replace(hour=0, minute=0, second=0, microsecond=0)
    return get_closed_profit_period(date_from, date_to, symbol)

# Пример использования
if __name__ == "__main__":
    # Подключение к MT5
    if not mt5.initialize():
        print("Ошибка подключения к MT5")
    else:
        # Профит за сегодня
        profit_today, deals_today = get_profit_today('XAUUSDrfd')
        print(f"Профит за сегодня: {profit_today:.2f}")
        
        # Профит за последние 7 дней
        profit_week, deals_week = get_profit_this_week('XAUUSDrfd')
        print(f"Профит за неделю: {profit_week:.2f}")
        
        # Профит за конкретный период
        date_from = datetime(2024, 1, 1)
        date_to = datetime.now()
        profit_period, deals_period = get_closed_profit_period(date_from, date_to, "XAUUSDrfd")
        print(f"Профит по XAUUSDrfd с начала года: {profit_period:.2f}")
        
