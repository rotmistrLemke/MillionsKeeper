import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd

def get_closed_deals_profit(target_symbol):
    """Получает и анализирует закрытые сделки с возможностью фильтрации по валюте"""
    
    if not mt5.initialize():
        print("Ошибка подключения к MT5:", mt5.last_error())
        return

    try:
        
        
        # Текущая дата и время
        now = datetime.now()

        # Находим начало текущей недели (понедельник)
        start_of_week = now - timedelta(days=now.weekday())  # Понедельник = 0, Воскресенье = 6
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

        # Конечная дата = сейчас + 2 дня
        end_date = now + timedelta(days=2)

        # Получаем сделки за период
        deals = mt5.history_deals_get(start_of_week, end_date)

        
        
        if not deals:
            print("Нет сделок в истории.")
            return

        # Фильтруем закрытые сделки
        closed_deals = [deal for deal in deals if deal.entry == mt5.DEAL_ENTRY_OUT]
        
        # Создаём DataFrame
        df = pd.DataFrame(list(closed_deals), columns=closed_deals[0]._asdict().keys())

        # Фильтрация по валюте если указана
        if target_symbol:
            df = df[df['symbol'] == target_symbol]
            if df.empty:
                print(f"\nНет закрытых сделок по {target_symbol}")
                return


        profit = df['profit'].sum()

        return profit
    
    finally:
        return



# Примеры использования:
#get_closed_deals_profit()  # Все сделки
#get_closed_deals_profit("EURUSDrfd")  # Только EURUSD
get_closed_deals_profit("GBPUSDrfd")  # Только GBPUSD