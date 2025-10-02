import json
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import time
import os
from typing import Dict, List, Any

class DataRecorder:
    def __init__(self, data_file: str = "market_data.json"):
        self.data_file = data_file
        self.ensure_data_file()
    
    def ensure_data_file(self):
        """Создает файл данных если он не существует"""
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w') as f:
                json.dump({}, f)
    
    def record_candle_data(self, symbol: str, timeframe: int, df: pd.DataFrame):
        """Записывает данные свечи в JSON"""
        try:
            # Загружаем существующие данные
            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            # Создаем ключ для символа и таймфрейма
            symbol_key = f"{symbol}_{timeframe}"
            
            if symbol_key not in data:
                data[symbol_key] = []
            
            # Берем последнюю завершенную свечу
            if len(df) >= 2:
                last_completed_candle = df.iloc[-2]
            # Если время в формате timestamp (int)
            if isinstance(last_completed_candle['time'], int):
                dt = datetime.fromtimestamp(last_completed_candle['time'])
                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                # Если уже datetime
                time_str = last_completed_candle['time'].strftime('%Y-%m-%d %H:%M:%S')

                candle_data = {
                    'time': time_str,
                    'open': float(last_completed_candle['open']),
                    'high': float(last_completed_candle['high']),
                    'low': float(last_completed_candle['low']),
                    'close': float(last_completed_candle['close']),
                    'tick_volume': int(last_completed_candle['tick_volume']),
                    'real_volume': int(last_completed_candle['real_volume']),
                    'recorded_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Проверяем, нет ли уже такой свечи
                existing_times = [candle['time'] for candle in data[symbol_key]]
                if candle_data['time'] not in existing_times:
                    data[symbol_key].append(candle_data)
                    
                    # Сохраняем только последние 10000 свечей для экономии памяти
                    if len(data[symbol_key]) > 10000:
                        data[symbol_key] = data[symbol_key][-10000:]
                
                # Сохраняем данные
                with open(self.data_file, 'w') as f:
                    json.dump(data, f, indent=2)
                    
        except Exception as e:
            print(f"Ошибка записи данных: {e}")
    
    def get_candle_data(self, symbol: str, timeframe: int, limit: int = 1000) -> List[Dict]:
        """Получает исторические данные из JSON"""
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            symbol_key = f"{symbol}_{timeframe}"
            if symbol_key in data:
                return data[symbol_key][-limit:]
            return []
        except Exception as e:
            print(f"Ошибка чтения данных: {e}")
            return []
    
    def get_all_symbols(self) -> List[str]:
        """Возвращает список всех символов в данных"""
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            symbols = set()
            for key in data.keys():
                symbol = key.split('_')[0]
                symbols.add(symbol)
            
            return list(symbols)
        except:
            return []