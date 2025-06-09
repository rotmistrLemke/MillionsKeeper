from telegram import  InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import asyncio
import json
from mt5Connector import MT5Connector
from anilizer import Extremum,ZeroIntersection,HundredIntersection,Alligator
from chartCreator import createChart
from appEnum import TargetType,IndicatorType


settings = {
    "CCI_ReferenceLimit" : 60,
    "CCI_CoefficientLimit" : 0.3,    
    "Stochastic_CoefficientLimit" : 0.1
}
#account1 = {"login":2000096507,"password":"x$Kz8CD7XB","server":"AlfaForexRU-Real"}
account = {"login":2000099548,"password":"VeeDM6A$E1","server":"AlfaForexRU-Real"}

#mt5Connector1 = MT5Connector(account1)
mt5Connector = MT5Connector(account)
zeroIntersection = ZeroIntersection()
hundredIntersection = HundredIntersection()
extremum = Extremum(settings)
#aligator = Alligator(mt5Connector)

async def searching(update, context) :     
    while True:  
        pairs = mt5Connector.getSymbols(50)
        for pair in pairs:
            if "#JNJ" in pair:
                continue
            print(f"\nПроверка пары CCI: {pair}")

            cci,signal,main = mt5Connector.getData(pair,30)                        
            resultExtremum = extremum.check(cci, signal)
            await ExtremumDisplay(resultExtremum, cci, update, pair)            
        await asyncio.sleep(5)

async def HundredIntersectionDisplay(result, cciValues, update, pair):
    if result["value"]:
        await createChart(cciValues,update)    
        callbackData = {"pair":pair,"targetType":str(TargetType.LONG),"indicator":str(IndicatorType.HUNDRED_INTERSECTION)}    
        long_button = InlineKeyboardButton(text="Лонг", callback_data=f"{json.dumps(callbackData)}")
        short_button = InlineKeyboardButton(text="Шорт", callback_data=f"{json.dumps(callbackData)}")
        if result["target"] == TargetType.LONG:            
            reply_markup = InlineKeyboardMarkup([[long_button]])
            await update.message.reply_text(f"{pair}\nРост перекупленности, лонгуем\nЗначение: {cciValues[0]}", reply_markup=reply_markup)
        if result["target"] == TargetType.SHORT:
            reply_markup = InlineKeyboardMarkup([[short_button]])
            await update.message.reply_text(f"{pair}\nРост перепроданности, шортим\nЗначение: {cciValues[0]}", reply_markup=reply_markup)   

async def ExtremumDisplay(result, cciValues, update, pair) :
    if not result["value"]:  
        return
    if(mt5Connector.symbolInPostions(pair,result["target"],IndicatorType.EXTREMUM_REVERSE)):
        print("Уже размещен заказ на данную пару")
        return  
          
    # long_button = InlineKeyboardButton(text="Лонг", callback_data=f"{json.dumps({"pair":pair,"targetType":str(TargetType.LONG),"indicator":str(IndicatorType.EXTREMUM_REVERSE)})}")
    # short_button = InlineKeyboardButton(text="Шорт", callback_data=f"{json.dumps({"pair":pair,"targetType":str(TargetType.SHORT),"indicator":str(IndicatorType.EXTREMUM_REVERSE)})}")

    if result["target"] == TargetType.LONG:       
        # reply_markup = InlineKeyboardMarkup([[long_button]])
        # await update.message.reply_text(f"{pair}\nПерепроданность, лонгуем\nЗначение: {cciValues[0]}", reply_markup=reply_markup)
        response = mt5Connector.orderOpen(pair,TargetType.LONG,IndicatorType.EXTREMUM_REVERSE,100,700)
        #await update.message.reply_text(f"{pair}\nПерепроданность, ставлю ордер на лонг\nОрдер: {response["order"]}") 
        #await createChart(cciValues,update)
        
    if result["target"] == TargetType.SHORT:                
        # reply_markup = InlineKeyboardMarkup([[short_button]])
        # await update.message.reply_text(f"{pair}\nПерекупленность, шортим\nЗначение: {cciValues[0]}", reply_markup=reply_markup)   
        response = mt5Connector.orderOpen(pair,TargetType.SHORT,IndicatorType.EXTREMUM_REVERSE,100,700)
        #await update.message.reply_text(f"{pair}\nПерекупленность, ставлю ордер на шорт\nОрдер: {response["order"]}")   
        #await createChart(cciValues,update)

async def ZeroIntersectionDisplay(result, cciValues, update, pair) :
    if result["value"]:
        await createChart(cciValues,update)    
        long_button = InlineKeyboardButton(text="Лонг", callback_data=f"{json.dumps({"pair":pair,"targetType":str(TargetType.LONG),"indicator":str(IndicatorType.ZERO_INTERSECTION)})}")
        short_button = InlineKeyboardButton(text="Шорт", callback_data=f"{json.dumps({"pair":pair,"targetType":str(TargetType.SHORT),"indicator":str(IndicatorType.ZERO_INTERSECTION)})}")
        if result["target"] == TargetType.LONG:
            reply_markup = InlineKeyboardMarkup([[long_button]])
            await update.message.reply_text(f"{pair}\nСработало пересечение нуля снизу вверх, лонгуем\nЗначение: {cciValues[0]}", reply_markup=reply_markup)   
        if result["target"] == TargetType.SHORT:
            reply_markup = InlineKeyboardMarkup([[short_button]])
            await update.message.reply_text(f"{pair}\nСработало пересечение нуля сверху вниз, шортим\nЗначение: {cciValues[0]}", reply_markup=reply_markup)  
 
async def check_order(update,context) :
    data = json.loads(update.callback_query.data)    
    if int(data["targetType"]) == TargetType.LONG:
        response = mt5Connector.orderOpen(data["pair"],TargetType.LONG,data["indicator"],100,700)        
        if response["order"]:
            await update.effective_message.reply_text(f"Ордер: {response['order']}\nПара: {response['symbol']}\nТип сделки: {response['targetType']}")
    if int(data["targetType"]) == TargetType.SHORT:
        response = mt5Connector.orderOpen(data["pair"],TargetType.SHORT,data["indicator"],100,700)        
        if response["order"]:
            await update.effective_message.reply_text(f"Ордер: {response['order']}\nПара: {response['symbol']}\nТип сделки: {response['targetType']}")

async def start(update, context):
        asyncio.create_task(searching(update, context))

def main() :
    token = "7299867067:AAHKJz7mN198zxJAF3LAWalMWA3QZlIKhzI"
    application = ApplicationBuilder().token(token).build()
    
    # Используем async handler вместо lambda с asyncio.run
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(check_order))
    
    application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
