import MetaTrader5 as mt5
import pandas as pd
import json
import httpx
from openai import OpenAI

class MarketForecaster:
    def __init__(self, api_key):
        """
        Инициализация прогнозировщика рынка
        :param api_key: Ваш API-ключ OpenAI
        """
        self.api_key = api_key
        self.proxy = "socks5h://127.0.0.1:9150"  # Настройте при необходимости
    
    def prepare_candles_data(self, candles):
        """
        Подготавливает данные свечей для отправки в API
        :param candles: Массив свечей
        :return: Текстовое представление последних 50 свечей
        """
        if not candles:
            return ""
        
        # Берем только последние 50 свечей для экономии токенов
        last_candles = candles[-50:]
        return "\n".join([
            f"{candle['time']}: O={candle['open']:.5f}, H={candle['high']:.5f}, "
            f"L={candle['low']:.5f}, C={candle['close']:.5f}"
            for candle in last_candles
        ])
    
    def get_market_forecast(self, symbol, candles):
        """
        Получает прогноз рыночного состояния через OpenAI API
        :param symbol: Торговый символ
        :param candles: Массив свечей
        :return: Строка с прогнозом (например "STRONG UPTREND")
        """
        candles_text = self.prepare_candles_data(candles)
        current_price = candles[-1]['close'] if candles else 0
        
        prompt = f"""
        Ты профессиональный финансовый аналитик. Проанализируй данные свечей для {symbol} и определи текущее рыночное состояние.
        Текущая цена: {current_price:.5f}
        Последние 50 свечей (время, open, high, low, close):
        {candles_text}
        
        Классифицируй состояние по следующим категориям:
        1. "STRONG UPTREND"    - Сильный восходящий тренд
        2. "STRONG DOWNTREND"  - Сильный нисходящий тренд
        3. "WEAK UPTREND"      - Слабый восходящий тренд
        4. "WEAK DOWNTREND"    - Слабый нисходящий тренд
        5. "STRONG FLAT"       - Явный флет (цена в узком диапазоне, низкая волатильность)
        6. "POTENTIAL FLAT"    - Потенциальный флет (начальные признаки флета)
        
        Учитывай:
        - Направление и крутизну тренда
        - Размеры тел свечей и их тени
        - Волатильность (ATR)
        - Соотношение бычьих и медвежьих свечей
        - Кластеры объемов (если есть в данных)
        
        Верни ТОЛЬКО одну из указанных строк без дополнительных комментариев.
        """
        
        try:
            with httpx.Client(proxy=self.proxy) as http_client:
                client = OpenAI(
                    api_key=self.api_key,
                    http_client=http_client
                )
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Ты опытный трейдер, специализирующийся на техническом анализе."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,  # Для более детерминированных ответов
                    max_tokens=20
                )
                
                # Извлекаем и очищаем ответ
                result = response.choices[0].message.content.strip()
                valid_results = [
                    "STRONG UPTREND", "STRONG DOWNTREND", 
                    "WEAK UPTREND", "WEAK DOWNTREND",
                    "STRONG FLAT", "POTENTIAL FLAT"
                ]
                
                return result if result in valid_results else "UNCLEAR"
                
        except Exception as e:
            print(f"Ошибка при запросе к API: {str(e)}")
            return "ERROR"

# Пример использования
if __name__ == "__main__":
    # Ваши реальные данные
    API_KEY = "sk-ваш_ключ"
    SYMBOL = "EURUSD"
    
    # Получение свечей из MT5 (пример)
    mt5.initialize()
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H1, 0, 2000)
    mt5.shutdown()
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s').dt.strftime('%Y-%m-%d %H:%M:%S')
    candles = df[['time', 'open', 'high', 'low', 'close']].to_dict('records')
    
    # Создание прогноза
    forecaster = MarketForecaster(API_KEY)
    forecast = forecaster.get_market_forecast(SYMBOL, candles)
    
    print(f"\nПрогноз для {SYMBOL}: {forecast}")