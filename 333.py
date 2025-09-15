import MetaTrader5 as mt5
from datetime import datetime, timedelta
from authenticator import MT5Auth
from account import Account

# выведем данные о пакете MetaTrader5
print("MetaTrader5 package author: ",mt5.__author__)
print("MetaTrader5 package version: ",mt5.__version__)

NOW = datetime.now() + timedelta(hours=3)
 
# установим подключение к терминалу MetaTrader 5
if not mt5.initialize():
    print("initialize() failed, error code =",mt5.last_error())
    quit()

account = Account.accountDemo2
auth = MT5Auth(account)
auth.login()

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
                (symbol is None or deal.symbol == symbol) and deal.entry ==1):
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

def get_profit_today(symbol=None):
    """Профит за сегодня"""
    date_from = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    date_to = NOW
    return get_closed_profit_period(date_from, date_to, symbol)

def get_profit_this_week(symbol=None):
    """Профит за текущую неделю"""
    today = datetime.now()
    date_from = today - timedelta(days=today.weekday())
    date_from = date_from.replace(hour=0, minute=0, second=0, microsecond=0)
    return get_closed_profit_period(date_from, today, symbol)

def get_profit_this_month(symbol=None):
    """Профит за текущий месяц"""
    today = NOW
    date_from = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return get_closed_profit_period(date_from, today, symbol)

def get_profit_last_days(days, symbol=None):
    """Профит за последние N дней"""
    date_to = NOW
    date_from = date_to - timedelta(days=days)
    date_from = date_from.replace(hour=0, minute=0, second=0, microsecond=0)
    return get_closed_profit_period(date_from, date_to, symbol)

def get_detailed_deals_stats(date_from, date_to, symbol=None):
    """
    Детальная статистика по сделкам за период
    """    
    try:
        deals = mt5.history_deals_get(date_from, date_to)
        
        if deals is None:
            return None
        
        stats = {
            'total_profit': 0.0,
            'total_deals': 0,
            'winning_deals': 0,
            'losing_deals': 0,
            'max_win': 0.0,
            'max_loss': 0.0,
            'by_symbol': {},
            'deals_list': []
        }
        
        for deal in deals:
            if deal.type in [0, 1] and deal.entry ==1:  # Только закрытые сделки
                profit = deal.profit
                stats['total_profit'] += profit
                stats['total_deals'] += 1
                
                if profit > 0:
                    stats['winning_deals'] += 1
                    stats['max_win'] = max(stats['max_win'], profit)
                else:
                    stats['losing_deals'] += 1
                    stats['max_loss'] = min(stats['max_loss'], profit)
                
                # Статистика по символам
                if deal.symbol not in stats['by_symbol']:
                    stats['by_symbol'][deal.symbol] = {
                        'profit': 0.0,
                        'deals': 0,
                        'wins': 0,
                        'losses': 0
                    }
                
                stats['by_symbol'][deal.symbol]['profit'] += profit
                stats['by_symbol'][deal.symbol]['deals'] += 1
                if profit > 0:
                    stats['by_symbol'][deal.symbol]['wins'] += 1
                else:
                    stats['by_symbol'][deal.symbol]['losses'] += 1
                
                stats['deals_list'].append({
                    'ticket': deal.ticket,
                    'symbol': deal.symbol,
                    'type': 'BUY' if deal.type == 0 else 'SELL',
                    'profit': profit,
                    'time': datetime.fromtimestamp(deal.time),
                    'volume': deal.volume
                })
        
        # Расчет дополнительных метрик
        if stats['total_deals'] > 0:
            stats['win_rate'] = (stats['winning_deals'] / stats['total_deals']) * 100
            stats['avg_win'] = stats['total_profit'] / stats['winning_deals'] if stats['winning_deals'] > 0 else 0
            stats['avg_loss'] = stats['total_profit'] / stats['losing_deals'] if stats['losing_deals'] > 0 else 0
        
        return stats
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

# Пример использования
if __name__ == "__main__":
    # Подключение к MT5
    if not mt5.initialize():
        print("Ошибка подключения к MT5")
    else:
        # Профит за сегодня
        profit_today, deals_today = get_profit_today()
        print(f"Профит за сегодня: {profit_today:.2f}")
        
        # Профит за последние 7 дней
        profit_week, deals_week = get_profit_last_days(7)
        print(f"Профит за неделю: {profit_week:.2f}")
        
        # Профит за конкретный период
        date_from = datetime(2024, 1, 1)
        date_to = NOW
        profit_period, deals_period = get_closed_profit_period(date_from, date_to, "XAUUSDrfd")
        print(f"Профит по XAUUSDrfd с начала года: {profit_period:.2f}")
        
        # Детальная статистика
        stats = get_detailed_deals_stats(date_from, date_to, "XAUUSDrfd")
        if stats:
            print(f"Всего сделок: {stats['total_deals']}")
            print(f"Винрейт: {stats.get('win_rate', 0):.1f}%")
            print(f"Общий профит: {stats['total_profit']:.2f}")
        

