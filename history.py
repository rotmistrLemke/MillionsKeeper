import MetaTrader5 as mt5
from datetime import datetime, timedelta


class History:

    def get_closed_profit_period(self, date_from, date_to, symbol=None):
        """
        Получить сумму профита по завершенным сделкам за период
        """
        try:
            deals = mt5.history_deals_get(date_from, date_to + timedelta(hours=3))
            if deals is None:
                return 0.0, []

            total_profit = 0.0
            closed_deals = []
            for deal in deals:
                if (deal.type in (0, 1) and deal.entry == 1
                        and (symbol is None or deal.symbol == symbol)):
                    total_profit += deal.profit
                    closed_deals.append({
                        'ticket': deal.ticket,
                        'symbol': deal.symbol,
                        'type': 'BUY' if deal.type == 0 else 'SELL',
                        'profit': deal.profit,
                        'time': datetime.fromtimestamp(deal.time),
                        'volume': deal.volume,
                    })
            return total_profit, closed_deals
        except Exception as e:
            print(f"Ошибка при получении истории сделок: {e}")
            return 0.0, []

    def get_profit_today(self, symbol=None):
        """Профит за сегодня"""
        date_from = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = datetime.now() + timedelta(hours=3)
        return self.get_closed_profit_period(date_from, date_to, symbol)

    def get_profit_this_week(self, symbol=None):
        """Профит за текущую неделю"""
        today = datetime.now() + timedelta(hours=3)
        date_from = today - timedelta(days=today.weekday())
        date_from = date_from.replace(hour=0, minute=0, second=0, microsecond=0)
        return self.get_closed_profit_period(date_from, today, symbol)

    def get_profit_this_month(self, symbol=None):
        """Профит за текущий месяц"""
        today = datetime.now() + timedelta(hours=3)
        date_from = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.get_closed_profit_period(date_from, today, symbol)

    def get_profit_last_days(self, days, symbol=None):
        """Профит за последние N дней"""
        date_to = datetime.now() + timedelta(hours=3)
        date_from = date_to - timedelta(days=days)
        date_from = date_from.replace(hour=0, minute=0, second=0, microsecond=0)
        return self.get_closed_profit_period(date_from, date_to, symbol)

    def get_detailed_deals_stats(self, date_from, date_to, symbol=None):
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
