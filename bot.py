import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import requests


bot = Bot(token='BOTTOKEN')
dp = Dispatcher()

users = {}

class ProfileStates(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    city = State()

class FoodStates(StatesGroup):
    waiting_for_food_amount = State()

class CalorieGoalState(StatesGroup):
    input_value = State()


@dp.message(Command('start'))
async def cmd_start(message: Message):
    await message.reply('Привет! Я помогу тебе отслеживать воду, калории и тренировки. Начни с команды /set_profile для настройки профиля')


@dp.message(Command('set_profile'))
async def cmd_set_profile(message: Message, state: FSMContext):
    await message.reply('Введите ваш вес (в кг):')
    await state.set_state(ProfileStates.weight)

@dp.message(ProfileStates.weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        await state.update_data(weight=float(message.text))
        await message.reply('Введите ваш рост (в см):')
        await state.set_state(ProfileStates.height)
    except ValueError:
        await message.reply('Пожалуйста, введите корректное число для веса')

@dp.message(ProfileStates.height)
async def process_height(message: Message, state: FSMContext):
    try:
        await state.update_data(height=float(message.text))
        await message.reply('Введите ваш возраст:')
        await state.set_state(ProfileStates.age)
    except ValueError:
        await message.reply('Пожалуйста, введите корректное число для роста')

@dp.message(ProfileStates.age)
async def process_age(message: Message, state: FSMContext):
    try:
        await state.update_data(age=int(message.text))
        await message.reply('Сколько минут активности у вас в день?')
        await state.set_state(ProfileStates.activity)
    except ValueError:
        await message.reply('Пожалуйста, введите корректное число для возраста')

@dp.message(ProfileStates.activity)
async def process_activity(message: Message, state: FSMContext):
    try:
        await state.update_data(activity=int(message.text))
        await message.reply('В каком городе вы находитесь?')
        await state.set_state(ProfileStates.city)
    except ValueError:
        await message.reply('Пожалуйста, введите корректное число для активности!')

@dp.message(ProfileStates.city)
async def process_city(message: Message, state: FSMContext):
    city = message.text
    await state.update_data(city=city)
    data = await state.get_data()
    user_id = message.from_user.id

    water_goal = calculate_water_goal(data['weight'], data['activity'], city)
    calorie_goal = calculate_calorie_goal(data['weight'], data['height'], data['age'])

    users[user_id] = {
        'weight': data['weight'],
        'height': data['height'],
        'age': data['age'],
        'activity': data['activity'],
        'city': city,
        'water_goal': water_goal,
        'calorie_goal': calorie_goal,
        'logged_water': 0,
        'logged_calories': 0,
        'burned_calories': 0,
    }

    await message.reply(f'Профиль обновлен!\n\n'
                        f'Ваша дневная норма воды: {water_goal} мл\n'
                        f'Ваша дневная норма калорий: {calorie_goal} ккал')
    await state.clear()


@dp.message(Command('set_calorie_goal'))
async def set_calorie_goal_handler(message: Message, state: FSMContext):
    await message.reply('Введите вашу дневную норму калорий (в ккал). Если хотите, чтобы я рассчитал норму для вас автоматически, введите 0')
    await state.set_state(CalorieGoalState.input_value)

@dp.message(CalorieGoalState.input_value)
async def save_calorie_goal(message: Message, state: FSMContext):
    try:
        calorie_goal = int(message.text)
        user_id = message.from_user.id

        if user_id not in users:
            await message.reply('Пожалуйста, настройте профиль с помощью команды /set_profile прежде, чем устанавливать цель калорий')
            await state.clear()
            return

        if calorie_goal == 0:
            data = users[user_id]
            calorie_goal = calculate_calorie_goal(data['weight'], data['height'], data['age'])

        users[user_id]['calorie_goal'] = calorie_goal
        await message.reply(f'Ваша новая цель по калориям установлена: {calorie_goal} ккал')
        await state.clear()
    except ValueError:
        await message.reply('Пожалуйста, введите корректное числовое значение для нормы калорий')


def calculate_water_goal(weight, activity_minutes, city):
    base_water = weight * 30
    activity_water = (activity_minutes // 30) * 500  # +500 мл за 30 минут активности
    weather_water = 0

    temperature = get_city_temperature(city)
    if temperature and temperature > 25:
        weather_water = 500
    elif temperature and temperature > 30:
        weather_water = 1000  # Тут рандом

    total_water = base_water + activity_water + weather_water
    return int(total_water)


def get_city_temperature(city): # Смотрим на темпу в городе, чтобы учесть в формуле
    API_KEY = 'APITOKEN'
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=ru'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        temperature = data['main']['temp']
        return temperature
    else:
        print(f'Не удалось получить погоду для города {city}')
        return None

# формула Миффлина-Сан Жеора
def calculate_calorie_goal(weight, height, age):
    calorie_goal = 10 * weight + 6.25 * height - 5 * age + 5  # эта инфа для мужчин, для женщин вычесть 161 вместо +5 (НЕ ЗАБУДЬ)
    return int(calorie_goal)


@dp.message(Command('log_water'))
async def cmd_log_water(message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        await message.reply('Пожалуйста, сначала настройте профиль командой /set_profile')
        return
    try:
        amount = int(message.text.split()[1])
        users[user_id]['logged_water'] += amount
        remaining = users[user_id]['water_goal'] - users[user_id]['logged_water']
        await message.reply(f'Записано: {amount} мл воды.\nОсталось: {remaining} мл до нормы.')
    except (IndexError, ValueError):
        await message.reply('Пожалуйста, используйте формат команды: /log_water <количество_в_мл>')


@dp.message(Command('log_food'))
async def cmd_log_food(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in users:
        await message.reply('Пожалуйста, сначала настройте профиль командой /set_profile')
        return

    try:
        product_name = ' '.join(message.text.split()[1:])
        food_info = get_food_info(product_name)
        if food_info:
            await state.update_data(food_calories=food_info['calories'])
            await state.set_state(FoodStates.waiting_for_food_amount)
            await message.reply(f"🍏 {food_info['name']} — {food_info['calories']} ккал на 100 г. Сколько грамм вы съели?")
        else:
            await message.reply('Не удалось найти информацию о продукте')
    except IndexError:
        await message.reply('Пожалуйста, используйте формат команды: /log_food <название_продукта>')

@dp.message(FoodStates.waiting_for_food_amount)
async def process_food_amount(message: Message, state: FSMContext):
    try:
        grams = float(message.text)
        data = await state.get_data()
        calories_per_100g = data['food_calories']
        total_calories = (calories_per_100g * grams) / 100

        user_id = message.from_user.id
        users[user_id]['logged_calories'] += total_calories
        await message.reply(f'Записано: {total_calories:.1f} ккал.')
        await state.clear()
    except ValueError:
        await message.reply('Пожалуйста, введите корректное количество в граммах')


def get_food_info(product_name):
    url = f'https://world.openfoodfacts.org/cgi/search.pl?action=process&search_terms={product_name}&json=true'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        products = data.get('products', [])
        if products:
            first_product = products[0]
            return {
                'name': first_product.get('product_name', 'Неизвестно'),
                'calories': first_product.get('nutriments', {}).get('energy-kcal_100g', 0)
            }
    return None


@dp.message(Command('log_workout'))
async def cmd_log_workout(message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        await message.reply('Пожалуйста, сначала настройте профиль командой /set_profile')
        return
    try:
        parts = message.text.split()
        workout_type = parts[1]
        duration = int(parts[2])

        met_values = {
            'Бег': 10,
            'Ходьба': 3.5,
            'Велосипед': 8
        }
        met = met_values.get(workout_type, 5)  # константа для метоболизма будет 5

        weight = users[user_id]['weight']
        calories_burned = (met * 3.5 * weight * duration) / 200

        users[user_id]['burned_calories'] += calories_burned
        await message.reply(f"Записано: тренировка '{workout_type}' длительностью {duration} мин. "
                            f"Сожжено калорий: {calories_burned:.1f} ккал.")
    except (IndexError, ValueError):
        await message.reply('Пожалуйста, используйте формат команды: /log_workout <тип> <время_в_минутах>')


@dp.message(Command('stats'))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    if user_id not in users:
        await message.reply('Пожалуйста, сначала настройте профиль командой /set_profile')
        return

    user_data = users[user_id]

    water_intake = user_data['logged_water']
    water_goal = user_data['water_goal']
    calories_consumed = user_data['logged_calories']
    calories_burned = user_data['burned_calories']
    calorie_goal = user_data['calorie_goal']

    net_calories = calories_consumed - calories_burned
    calories_remaining = calorie_goal - net_calories

    await message.reply(f'📊 *Ваша статистика на сегодня:*\n'
                        f'💧 Выпито воды: {water_intake} мл из {water_goal} мл\n'
                        f'🍏 Потреблено калорий: {calories_consumed:.1f} ккал\n'
                        f'🔥 Сожжено калорий: {calories_burned:.1f} ккал\n'
                        f'⚖️ Чистые калории: {net_calories:.1f} ккал\n'
                        f'🎯 Осталось потребить: {calories_remaining:.1f} ккал до цели',
                        parse_mode='Markdown')
    

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
