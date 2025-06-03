from mt5Connector import MT5Connector
import MetaTrader5 as mt5
from appEnum import TargetType,IndicatorType, Settings
import time
import pandas as pd
from anilizer import Alligator
from logger import Logger

account = {"login":2000099548,"password":"VeeDM6A$E1","server":"AlfaForexRU-Real"}
mt5Connector = MT5Connector(account)
logger = Logger()

def checkOpen(jaw, teeth, lips, angle, pair):
    
    serverTime = mt5Connector.ServerTime(pair)
    
    if mt5Connector.symbolInPostions(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN) or mt5Connector.symbolInPostions(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN):
        #Уже есть ордер по данной паре и данному индикатору
        return
    #if lips > teeth and lips > jaw and angle >= 10 and candlediff <= Settings.dictLipsCandleDiff.get(pair, 35):
    if lips < teeth and angle > 5 and lipsVsTeethDiff <= Settings.dictLipsTeethDiff.get(pair, 10) or (angle > 5 and lips > teeth) or (lips < teeth and angle > 15) or (angle > 30):
         
        mt5Connector.orderOpenForAlligatorMain(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
        print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \ncomment: Ордер LONG выставлен по условию, \n{"-" * 50}")
        Alligator.saveToExcel(pair, "OPEN_LONG", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер LONG выставлен по условию")
            
    #if lips < teeth and lips < jaw and angle <= -10 and candlediff <= Settings.dictLipsCandleDiff.get(pair, 35):
    if lips > teeth and angle < -5 and lipsVsTeethDiff <= Settings.dictLipsTeethDiff.get(pair, 10) or (angle < -5 and lips < teeth) or (lips > teeth and angle < -15) or (angle < -30):
        
        mt5Connector.orderOpenForAlligatorMain(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
        print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \ncomment: Ордер SHORT выставлен по условию, \n{"-" * 50}")
        Alligator.saveToExcel(pair, "OPEN_SHORT", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер SHORT выставлен по условию")
            
def checkClose(jaw, teeth,lips, angle, lipsVsTeethDiff, pair):
    serverTime = mt5Connector.ServerTime(pair)
    
    if lips < teeth and angle > 5 and lipsVsTeethDiff <= Settings.dictLipsTeethDiff.get(pair, 10) or (angle > 5 and lips > teeth) or (lips < teeth and angle > 15) or (angle > 30):
        
        ticket = mt5Connector.getTicket(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
        
        if ticket:
            
            mt5Connector.orderClose(ticket,pair)
            print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \nLipsVsTeethDiff: {lipsVsTeethDiff}, \ncomment: Ордер SHORT снят, \n{"-" * 50}")
            Alligator.saveToExcel(pair, "CLOSE_SHORT", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер SHORT снят")
           
            mt5Connector.orderOpenForAlligatorMain(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
            print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \ncomment: Ордер LONG выставлен по закрытию предыдущего, \n{"-" * 50}")
            Alligator.saveToExcel(pair, "OPEN_LONG", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер LONG выставлен по закрытию предыдущего")
            
    if lips > teeth and angle < -5 and lipsVsTeethDiff <= Settings.dictLipsTeethDiff.get(pair, 10) or (angle < -5 and lips < teeth) or (lips > teeth and angle < -15) or (angle < -30):
        ticket = mt5Connector.getTicket(pair,TargetType.LONG,IndicatorType.ALLIGATOR_MAIN)
        
        if ticket:

            mt5Connector.orderClose(ticket, pair)
            print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \nLipsVsTeethDiff: {lipsVsTeethDiff}, \ncomment: Ордер LONG снят, \n{"-" * 50}")
            Alligator.saveToExcel(pair, "CLOSE_LONG", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер LONG снят")
            
            mt5Connector.orderOpenForAlligatorMain(pair,TargetType.SHORT,IndicatorType.ALLIGATOR_MAIN)
            print(f"\n{"-" * 50}, \ntime:{serverTime}, \npair: {pair}, \njaw: {jaw}, \nteeth: {teeth}, \nlips: {lips}, \nangle: {angle}, \ncomment: Ордер SHORT выставлен по закрытию предыдущего, \n{"-" * 50}")
            Alligator.saveToExcel(pair, "OPEN_SHORT", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "Ордер SHORT выставлен по закрытию предыдущего")

if __name__ == '__main__':

    pairs = Settings.dictPairXvalue.keys()
    last_log_time = None
    nextLogTime = logger.getNextLogTime(mt5Connector.ServerTime('EURUSDrfd'))
    prev_bar_time = None

    
    while True:
        
        for pair in pairs:
            
            currentTime = mt5Connector.ServerTime(pair)
            
            jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff = mt5Connector.alligatorData(pair)
            # Проверяем, нужно ли записывать время
            if currentTime >= nextLogTime:
                Alligator.saveToExcel(pair, "LOG", jaw, teeth, lips, angle, candleDiff, lipsVsTeethDiff, "")
            
            checkOpen(jaw, teeth, lips, angle, pair)    
            checkClose(jaw, teeth, lips, angle, lipsVsTeethDiff, pair)    
        # Обновляем время следующей записи

        nextLogTime = logger.getNextLogTime(currentTime)
        
        print(f"Все в порядке, время:{mt5Connector.ServerTime(pair)}")
        time.sleep(3600)
        

    
        
