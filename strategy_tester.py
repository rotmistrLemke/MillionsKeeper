import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Callable
from data_recorder import DataRecorder
from indicators import AdaptiveMovingAverage, Alligator, MACD
from trading import Trading
from settings import TargetType, Dictionary


trading = Trading()
dict = Dictionary()

class StrategyTester:
    def __init__(self, initial_balance: float = 10000):
        self.data_recorder = DataRecorder()
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions = []
        self.trades = []
        self.equity_curve = []
        self.alligator = Alligator()
        self.macd = MACD()
        self.ama = AdaptiveMovingAverage()
        
    def backtest_strategy(self, 
                         symbol: str, 
                         timeframe: int,
                         start_date: str = None,
                         end_date: str = None):
        """
        Бэктестинг стратегии с логикой входа и выхода
        """
        # Получаем данные
        candle_data = self.data_recorder.get_candle_data(symbol, timeframe, limit=5000)
        
        if not candle_data:
            print(f"Нет данных для {symbol}_{timeframe}")
            return
        
        # Конвертируем в DataFrame
        df = pd.DataFrame(candle_data)
        df['time'] = pd.to_datetime(df['time'])
        df = df.sort_values('time')
        
        # Фильтруем по датам если указано
        if start_date:
            start_dt = pd.to_datetime(start_date)
            df = df[df['time'] >= start_dt]
        
        if end_date:
            end_dt = pd.to_datetime(end_date)
            df = df[df['time'] <= end_dt]
        
        print(f"Запуск бэктеста для {symbol}, свечей: {len(df)}")
        
        # Симуляция торговли
        for i in range(2, len(df)):
            current_data = df.iloc[:i+1]
            current_candle = df.iloc[i]
            
            try:
                # Получаем сигналы входа
                entry_signal = self.alligator_macd_entry_strategy(symbol, current_data, current_candle)
                
                # Получаем сигналы выхода для открытых позиций
                exit_signal = self.macd_exit_strategy(symbol, current_data, current_candle)
                
                # Обрабатываем выход сначала
                if exit_signal and self.has_open_position(symbol):
                    position_type = self.get_position_type(symbol)
                    if (position_type == "BUY" and exit_signal == "CLOSE_BUY") or \
                       (position_type == "SELL" and exit_signal == "CLOSE_SELL"):
                        self.close_position(symbol, current_candle['close'], current_candle['time'])
                
                # Затем обрабатываем вход
                if entry_signal == "BUY" and not self.has_open_position(symbol):
                    self.open_position(symbol, "BUY", current_candle['close'], current_candle['time'])
                    
                elif entry_signal == "SELL" and not self.has_open_position(symbol):
                    self.open_position(symbol, "SELL", current_candle['close'], current_candle['time'])
                
                # Обновляем кривую эквити
                self.update_equity(symbol, current_candle['close'], current_candle['time'])
                
            except Exception as e:
                print(f"Ошибка на свече {current_candle['time']}: {e}")
                continue
        
        # Закрываем все открытые позиции в конце
        self.close_all_positions(df.iloc[-1]['close'], df.iloc[-1]['time'])
        
        # Выводим результаты
        self.print_results()
    
    def alligator_macd_entry_strategy(self, symbol: str, df: pd.DataFrame, current_candle: Dict) -> str:
        """Стратегия входа на основе аллигатора и MACD (из trading_loop)"""
        try:
            # Эмулируем расчет MACD на исторических данных
            # В реальном коде используется macd.calculate_macd_manual(symbol, TIME_FRAME)
            current_macd, prev_macd, prev2_macd = self.calculate_macd_from_data(df, symbol)
            
            # Логика входа из trading_loop
            if prev2_macd < 0 and prev_macd > 0:
                return "BUY"
            elif prev2_macd > 0 and prev_macd < 0:
                return "SELL"
            
            return "HOLD"
        except Exception as e:
            print(f"Ошибка в стратегии входа: {e}")
            return "HOLD"
    
    def macd_exit_strategy(self, symbol: str, df: pd.DataFrame, current_candle: Dict) -> str:
        """Стратегия выхода на основе MACD (из moneySaverLoop)"""
        if not self.has_open_position(symbol):
            return None
            
        try:
            # Эмулируем расчет MACD на исторических данных
            current_macd, prev_macd, prev2_macd = self.calculate_macd_from_data(df, symbol)
            
            position_type = self.get_position_type(symbol)
            
            # Логика выхода из moneySaverLoop
            if position_type == "BUY" and (prev2_macd > prev_macd):
                return "CLOSE_BUY"
            elif position_type == "SELL" and (prev2_macd < prev_macd):
                return "CLOSE_SELL"
            
            return None
        except Exception as e:
            print(f"Ошибка в стратегии выхода: {e}")
            return None
    
    def calculate_macd_from_data(self, df: pd.DataFrame, symbol: str) -> tuple:
        """
        Эмуляция расчета MACD на исторических данных
        В реальной системе используется macd.calculate_macd_manual()
        """
        # Здесь должна быть реализация расчета MACD на основе df
        # Для простоты эмулируем случайные значения (замените на реальный расчет)
        import random
        current_macd = random.uniform(-0.01, 0.01)
        prev_macd = random.uniform(-0.01, 0.01)
        prev2_macd = random.uniform(-0.01, 0.01)
        
        return current_macd, prev_macd, prev2_macd
    
    def open_position(self, symbol: str, position_type: str, price: float, time: datetime):
        """Открывает позицию"""
        position = {
            'symbol': symbol,
            'type': position_type,
            'entry_price': price,
            'entry_time': time,
            'size': self.balance * 0.1,  # 10% от баланса
            'volume':  trading.calculateSafeTradeWithMargin(
                symbol, 
                risk_percent=90, 
                stop_loss_pips = dict.symbolStopLossPoint[symbol], 
                order_type=TargetType.LONG
            )
        }
        self.positions.append(position)
        print(f"📈 OPEN {position_type} {symbol} по цене {price:.5f}, объем: {position['volume']:.2f}")
    
    
    def close_position(self, symbol: str, price: float, time: datetime):
        """Закрывает позицию по символу"""
        for position in self.positions:
            if position['symbol'] == symbol:
                pnl = self.calculate_pnl(position, price)
                self.balance += pnl
                
                trade = {
                    'symbol': symbol,
                    'type': position['type'],
                    'entry_price': position['entry_price'],
                    'exit_price': price,
                    'entry_time': position['entry_time'],
                    'exit_time': time,
                    'pnl': pnl,
                    'size': position['size'],
                    'volume': position['volume']
                }
                self.trades.append(trade)
                self.positions.remove(position)
                
                status = "PROFIT" if pnl > 0 else "LOSS"
                print(f"📉 CLOSE {position['type']} {symbol} PnL: {pnl:.2f} ({status})")
                break
    
    def close_all_positions(self, price: float, time: datetime):
        """Закрывает все открытые позиции"""
        for position in self.positions[:]:
            self.close_position(position['symbol'], price, time)
    
    def has_open_position(self, symbol: str) -> bool:
        """Проверяет есть ли открытая позиция по символу"""
        return any(pos['symbol'] == symbol for pos in self.positions)
    
    def get_position_type(self, symbol: str) -> str:
        """Возвращает тип открытой позиции"""
        for position in self.positions:
            if position['symbol'] == symbol:
                return position['type']
        return None
    
    def calculate_pnl(self, position: Dict, current_price: float) -> float:
        """Рассчитывает PnL для позиции"""
        if position['type'] == "BUY":
            return (current_price - position['entry_price']) * position['volume']
        else:  # SELL
            return (position['entry_price'] - current_price) * position['volume']
    
    def update_equity(self, symbol: str, price: float, time: datetime):
        """Обновляет кривую эквити"""
        total_value = self.balance
        for position in self.positions:
            total_value += self.calculate_pnl(position, price)
        
        self.equity_curve.append({
            'time': time,
            'equity': total_value,
            'balance': self.balance
        })
    
    def print_results(self):
        """Выводит результаты тестирования"""
        if not self.trades:
            print("Нет сделок для анализа")
            return
        
        total_pnl = sum(trade['pnl'] for trade in self.trades)
        profitable_trades = [t for t in self.trades if t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] <= 0]
        
        win_rate = len(profitable_trades) / len(self.trades) * 100
        avg_profit = sum(t['pnl'] for t in profitable_trades) / len(profitable_trades) if profitable_trades else 0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        profit_factor = abs(avg_profit / avg_loss) if avg_loss != 0 else float('inf')
        
        max_drawdown = self.calculate_max_drawdown()
        
        print("\n" + "="*60)
        print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ СТРАТЕГИИ (ВХОД + ВЫХОД)")
        print("="*60)
        print(f"Начальный депозит: ${self.initial_balance:.2f}")
        print(f"Конечный баланс: ${self.balance:.2f}")
        print(f"Общий PnL: ${total_pnl:.2f}")
        print(f"Доходность: {(total_pnl/self.initial_balance)*100:.2f}%")
        print(f"Максимальная просадка: {max_drawdown:.2f}%")
        print(f"Всего сделок: {len(self.trades)}")
        print(f"Прибыльных: {len(profitable_trades)}")
        print(f"Убыточных: {len(losing_trades)}")
        print(f"Винрейт: {win_rate:.1f}%")
        print(f"Средняя прибыль: ${avg_profit:.2f}")
        print(f"Средний убыток: ${avg_loss:.2f}")
        print(f"Профит-фактор: {profit_factor:.2f}")
        print("="*60)
        
        # Детали по сделкам
        print("\n📋 ПОСЛЕДНИЕ 10 СДЕЛОК:")
        recent_trades = sorted(self.trades, key=lambda x: x['exit_time'], reverse=True)[:10]
        for trade in recent_trades:
            emoji = "🟦" if trade['type'] == 'BUY' else "🟥"
            profit_emoji = "✅" if trade['pnl'] > 0 else "❌"
            time_str = trade['exit_time'].strftime('%d.%m %H:%M')
            print(f"{emoji} {trade['symbol']} {profit_emoji} {trade['pnl']:.2f} ({time_str})")
    
    def calculate_max_drawdown(self) -> float:
        """Рассчитывает максимальную просадку"""
        if not self.equity_curve:
            return 0
        
        peak = self.equity_curve[0]['equity']
        max_dd = 0
        
        for point in self.equity_curve:
            if point['equity'] > peak:
                peak = point['equity']
            dd = (peak - point['equity']) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
class AdvancedTestingPolygon:
    def __init__(self):
        self.tester = StrategyTester()
        self.test_results = {}
    
    def run_comprehensive_test(self, symbol: str, timeframe: int):
        """Запускает комплексное тестирование стратегии"""
        print(f"🧪 ЗАПУСК КОМПЛЕКСНОГО ТЕСТИРОВАНИЯ ДЛЯ {symbol}")
        
        # Тестируем на разных периодах
        test_periods = [
            ("Последние 30 дней", 30),
            ("Последние 90 дней", 90),
            ("Последние 180 дней", 180),
            ("Последний год", 365)
        ]
        
        results = {}
        
        for period_name, days in test_periods:
            print(f"\n📅 Тестирование: {period_name}")
            
            # Создаем нового тестера для каждого периода
            period_tester = StrategyTester(initial_balance=10000)
            
            # Запускаем тест
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            period_tester.backtest_strategy(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
            # Сохраняем результаты
            results[period_name] = {
                'final_balance': period_tester.balance,
                'total_trades': len(period_tester.trades),
                'win_rate': self.calculate_win_rate(period_tester.trades),
                'total_pnl': period_tester.balance - 10000,
                'max_drawdown': period_tester.calculate_max_drawdown()
            }
        
        self.test_results[symbol] = results
        self.print_comprehensive_results(symbol)
    
    def calculate_win_rate(self, trades: List[Dict]) -> float:
        """Рассчитывает винрейт"""
        if not trades:
            return 0
        profitable = len([t for t in trades if t['pnl'] > 0])
        return (profitable / len(trades)) * 100
    
    def print_comprehensive_results(self, symbol: str):
        """Выводит комплексные результаты"""
        if symbol not in self.test_results:
            return
        
        results = self.test_results[symbol]
        
        print("\n" + "="*70)
        print(f"🎯 КОМПЛЕКСНЫЕ РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ: {symbol}")
        print("="*70)
        
        for period_name, data in results.items():
            print(f"\n📊 {period_name}:")
            print(f"   💰 Конечный баланс: ${data['final_balance']:.2f}")
            print(f"   📈 Общий PnL: ${data['total_pnl']:.2f}")
            print(f"   📊 Сделок: {data['total_trades']}")
            print(f"   🎯 Винрейт: {data['win_rate']:.1f}%")
            print(f"   📉 Макс. просадка: {data['max_drawdown']:.2f}%")
    
    def compare_strategies(self, symbols: List[str], timeframe: int):
        """Сравнивает эффективность стратегии на разных символах"""
        print(f"🔍 СРАВНЕНИЕ СТРАТЕГИИ НА РАЗНЫХ СИМВОЛАХ")
        
        comparison_results = {}
        
        for symbol in symbols:
            print(f"\nАнализ {symbol}...")
            tester = StrategyTester(initial_balance=10000)
            
            tester.backtest_strategy(
                symbol=symbol,
                timeframe=timeframe,
                start_date=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
                end_date=datetime.now().strftime('%Y-%m-%d')
            )
            
            comparison_results[symbol] = {
                'final_balance': tester.balance,
                'total_trades': len(tester.trades),
                'win_rate': self.calculate_win_rate(tester.trades),
                'total_pnl': tester.balance - 10000,
                'profit_factor': self.calculate_profit_factor(tester.trades)
            }
        
        self.print_comparison_results(comparison_results)
    
    def calculate_profit_factor(self, trades: List[Dict]) -> float:
        """Рассчитывает профит-фактор"""
        gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        
        return gross_profit / gross_loss if gross_loss != 0 else float('inf')
    
    def print_comparison_results(self, results: Dict):
        """Выводит результаты сравнения"""
        print("\n" + "="*80)
        print("🏆 СРАВНЕНИЕ ЭФФЕКТИВНОСТИ СТРАТЕГИИ")
        print("="*80)
        
        # Сортируем по доходности
        sorted_results = sorted(results.items(), key=lambda x: x[1]['total_pnl'], reverse=True)
        
        for i, (symbol, data) in enumerate(sorted_results, 1):
            rank_emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            
            print(f"\n{rank_emoji} {symbol}:")
            print(f"   💰 Доходность: {data['total_pnl']:.2f} USD")
            print(f"   📈 ROI: {(data['total_pnl']/10000)*100:.1f}%")
            print(f"   📊 Сделок: {data['total_trades']}")
            print(f"   🎯 Винрейт: {data['win_rate']:.1f}%")
            print(f"   📊 Профит-фактор: {data['profit_factor']:.2f}")