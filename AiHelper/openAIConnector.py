from openai import OpenAI
from settings import Settings
import json



class OpenAIConnector:
    def __init__(self):
        """
        Инициализация анализатора
        :param symbol: Торговый символ (например: EURUSD)
        :param api_key: API ключ для DeepSeek (по умолчанию рабочий ключ)
        """
        

        
    
    def analyzeWithOpenAI(symbol, candles, cci):
    # Формируем текстовое представление последних 5 свечей
        last_candles = []

        for candle in candles[-30:]:
            last_candles.append(
                f"{candle['time']}: O={candle['open']:.5f}, H={candle['high']:.5f}, "
                f"L={candle['low']:.5f}, C={candle['close']:.5f}, "
                f"Vol={candle['tick_volume']} (Ratio={candle.get('volume_ratio', 0):.2f})"
            )
        
        prompt = f"""
        Проведи комплексный технический анализ пары {symbol} на основе {len(candles)} свечей (H4) с учетом тиковых объемов.
        Текущая цена: {candles[-1]['close']:.5f}
        
        Последние 30 свечей:
        {chr(10).join(last_candles)}
        
        Commodity Channel Index:
        {cci}
        
        Анализируй:
        1. Ключевые уровни поддержки/сопротивления (учитывай кластеры объемов)
        2. Тренд (направление, сила по ADX если возможно)
        3. Сигналы осцилляторов (RSI, MACD)
        4. Аномалии объемов (VSA-анализ)
        5. Commodity Channel Index
        
        Сформируй JSON-ответ строго в следующем формате:
        {{
        "orderType": "Limit|Market",
        "positionType": "BUY|SELL",
        "entryPoint": float (5 decimal places),
        "stopLoss": float (5 decimal places),
        "takeProfit": float (5 decimal places),
        "signalPower": int (1-5),
        "keySupport": [float, float, float] (5 decimal places),
        "keyResistance": [float, float, float] (5 decimal places),
        "trendAnalysis": string,
        "volumeAnalysis": string,
        "summary": string
        }}
        
        Правила:
        - Все цены должны иметь 5 знаков после точки (например: 1.12345)
        - Если сигнал неясен, signalPower=0
        - Если сигналов несколько выдай с максимальным значением signalPower
        - Анализируй объемы: высокие объемы на ценовых уровнях = сильные уровни
        - Учитывай дивергенции объема и цены
        - Для расчета RSI используй стандартные 14 периодов
        - Для MACD используй стандартные параметры (12,26,9)
        - Учитывай данные Commodity Channel Index
        """
      
        try:
            client = OpenAI(
                api_key = Settings.deepSeekapiKey,
                base_url = Settings.deepSeekUrl
            )

            response = client.chat.completions.create(
                model = Settings.modelDeepSeek,
                response_format = {"type": "json_object"},
                messages = [
                    {
                        "role": "system", 
                    "content": "Ты профессиональный трейдер-аналитик. Формируй ответ строго в требуемом JSON формате. "
                              "Все цены округляй до 5 знаков. Не оборачивай JSON в markdown-код (```). "
                              "Отправляй чистый JSON без дополнительного форматирования."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.3
            )
            
            # Валидация JSON
            result = response.choices[0].message  # .content только нужное
            #json.loads(result)  # Проверка синтаксиса
            return result
            
        except json.JSONDecodeError:
            print("Ошибка: Некорректный JSON в ответе")
            return None
        except Exception as e:
            print(f"Критическая ошибка: {str(e)}")
            return None




       