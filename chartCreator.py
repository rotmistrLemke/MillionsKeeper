import matplotlib.pyplot as plt
import numpy as np
import os

async def createChart(values,update):
    # Обратное значение массива
    data = values[::-1]
    if os.path.exists('chart.png'):
        os.remove('chart.png')

    try:
        plt.clf()
        # Настройка стиля графика
        plt.style.use('default')  # Используем стандартный стиль
        
        # Создаем линию графика
        line = plt.plot(
            range(1, len(data) + 1),
            data,
            color='#4BC0C0',  # rgb(75, 192, 192)
            linewidth=2,
            marker='o',
            markersize=5,
            label='CCI'
        )
        
        # Настраиваем сетку
        plt.grid(True, linestyle='-', alpha=0.3)
        
        # Добавляем специальные линии для значений 0, 100 и -100
        for value in [0, 100, -100]:
            plt.axhline(y=value, color='black', linewidth=3 if value == 0 else 1)
        
        # Настраиваем оси
        plt.xlabel('')
        plt.ylabel('')
        
        # Устанавливаем метки по оси X
        plt.xticks(range(1, len(data) + 1))
        
        # Добавляем легенду
        plt.legend()
        
        # Сохраняем график в файл
        plt.savefig('chart.png', bbox_inches='tight', dpi=100)
        print("График успешно создан и сохранен как chart.png")        
        plt.close()
        await update.message.reply_photo(photo=open('chart.png', 'rb'),caption="")


        
    except Exception as e:
        print(f"Ошибка при создании графика: {str(e)}")