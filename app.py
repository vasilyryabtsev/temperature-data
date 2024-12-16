import streamlit as st
import numpy as np
import pandas as pd
import requests
import time

URL = 'https://api.openweathermap.org/data/2.5/weather'

@st.cache_data
def SMA(data, n):
    '''
    Вычесляет простое скользящее среднее для температуры из таблицы data c задынным окном n.
    Таблица должна быть отсортированна по дате.
    '''
    # Предобработка данных
    data_copy = data.copy()
    data_copy['smoothed_temperature'] = data_copy['temperature']
    
    # Подсчет сглаженной температуры для первой доступной даты
    first_value = data_copy.head(n)['temperature'].mean()
    first_index = data_copy.iloc[n - 1].name
    data_copy.loc[first_index, 'smoothed_temperature'] = first_value
    
    # Подготовка данных для вычисления сглаживающих значений по рекурентной формуле
    global prev_SMA
    
    prev_SMA = data_copy.loc[first_index]['smoothed_temperature']
    data_copy[f'temp_{n}_days_ago'] = data_copy['temperature'].shift(n)
    
    # Вычесление остальных сглаженных температур
    def recurrent_SMA(x):
        '''
        Функция для pd.DataFrame.apply: вычисляет сглаженную температуру по значениям текущего и предыдущего объекта.
        '''
        global prev_SMA
        
        x['smoothed_temperature'] = prev_SMA - x[f'temp_{n}_days_ago'] / n + x['temperature'] / n
        
        prev_SMA = x['smoothed_temperature']
        
        return x
    
    data_copy.iloc[n:] = data_copy.iloc[n:].apply(recurrent_SMA, axis=1)
    
    return data_copy['smoothed_temperature']

@st.cache_data
def temperature_SMA(data):
    data_copy = data.copy()
    for city in pd.unique(data_copy['city']):
        sorted_data = data_copy[data_copy['city'] == city].sort_values('timestamp')
        smoothed_temperature = SMA(sorted_data, 30)
        data_copy.loc[smoothed_temperature.index, 'smoothed_temperature'] = smoothed_temperature
    return data_copy
                        
@st.cache_data
def load_data(uploaded_file):
    return pd.read_csv(uploaded_file)

@st.cache_data
def check_status(key):
    """
    Проверяет корректность API-ключа.
    """
    if key == None:
        return False
    
    params = {
        'lat': 55.751244,
        'lon': 37.618423,
        'appid': key
    }
    
    response = requests.get(URL, params=params)
    
    if response.status_code == 401:
        st.write(response.json().get('message'))
        
        return False

    st.write('Ключ введен корректно')
    
    return True

@st.cache_data
def get_weather(lat, lon, key):
    """
    Получает текущую температуру в заданных координатах.
    """
    params = {
        'lat': lat,
        'lon': lon,
        'appid': key,
        'units': 'metric',
        'lang': 'ru'
    }
    
    try:
        response = requests.get(URL, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        return data.get('main', {}).get('temp')
    except requests.RequestException as e:
        st.write(f"Возникла ошибка при получении данных")
        
        return {}

st.title('Анализ температуры в городе')
    
st.write('Загрузите собственный файл с историческими данными о температуре или воспользуетесь нашими данными.')

agree = st.checkbox('Загрузить свои данные')

data = None

if agree:
    uploaded_file = st.file_uploader("Выберите файл")
    
    if uploaded_file is not None:
        data = load_data(uploaded_file)
        
        st.write(data)    
else:
    data = load_data('temperature_data.csv')
    
    st.write(data)

if data is not None:
    option = st.selectbox(
        "Выберите город",
        data['city'].unique(),
        index=None,
        placeholder="Select contact method...",
    )
    
    key = st.text_input('Ввидете API-ключ OpenWeatherMap:', )

    if check_status(key):
        results = st.checkbox('Показать результаты')
        
        if results:
            st.write('Результаты')
            
            with st.spinner("Пожалуйста, подождите... идет расчет"):
                data = temperature_SMA(data)
                
                st.write(data)