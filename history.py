import MetaTrader5 as mt5
from datetime import datetime
import pandas as pd

def get_closed_deals_profit(target_symbol=None):
    """Получает и анализирует закрытые сделки с возможностью фильтрации по валюте"""
    
    if not mt5.initialize():
        print("Ошибка подключения к MT5:", mt5.last_error())
        return

    try:
        # Получаем все сделки из истории
        deals = mt5.history_deals_get(datetime(2025, 6, 8), datetime.now())
        
        if not deals:
            print("Нет сделок в истории.")
            return

        # Фильтруем закрытые сделки
        closed_deals = [deal for deal in deals if deal.entry == mt5.DEAL_ENTRY_OUT]
        
        # Создаём DataFrame
        df = pd.DataFrame(list(closed_deals), columns=closed_deals[0]._asdict().keys())
        df['time'] = pd.to_datetime(df['time'], unit='s').dt.strftime('%Y-%m-%d %H:%M:%S')

        # Фильтрация по валюте если указана
        if target_symbol:
            df = df[df['symbol'] == target_symbol]
            if df.empty:
                print(f"\nНет закрытых сделок по {target_symbol}")
                return

        # Группировка по валютам
        profit_stats = df.groupby('symbol').agg(
            Сделок=('profit', 'count'),
            Общий_Profit=('profit', 'sum'),
            Средний_Profit=('profit', 'mean'),
            Макс_Profit=('profit', 'max'),
            Мин_Profit=('profit', 'min')
        ).reset_index()

        # Вывод результатов
        print("\nРезультаты по закрытым сделкам:")
        if target_symbol:
            print(f"Фильтр: {target_symbol}")
        
        print("\nДетали сделок:")
        print(df[['time', 'symbol', 'volume', 'type', 'profit', 'comment']])
        
        print("\nСтатистика по валютам:")
        print(profit_stats.to_string(index=False))
        
        print(f"\nОбщий Profit: {df['profit'].sum():.2f}")

    finally:
        mt5.shutdown()

# Примеры использования:
get_closed_deals_profit()  # Все сделки
get_closed_deals_profit("EURUSDrfd")  # Только EURUSD
get_closed_deals_profit("GBPUSDrfd")  # Только GBPUSD