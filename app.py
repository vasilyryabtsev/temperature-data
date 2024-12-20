import streamlit as st
import numpy as np
import pandas as pd
import requests
import matplotlib.pyplot as plt
import time
import plotly.express as px
from datetime import datetime



URL = 'https://api.openweathermap.org/data/2.5/weather'

cities = {'New York': (40.730610, -73.935242),
          'London': (51.507351, -0.127758),
          'Paris': (48.856613, 2.352222),
          'Tokyo': (35.689487, 139.691711),
          'Moscow': (55.755825, 37.617298),
          'Sydney': (-33.868820, 151.209290),
          'Berlin': ( 52.520008, 13.404954),
          'Beijing': (39.916668, 116.383331),
          'Rio de Janeiro': (-22.908333, -43.196388),
          'Dubai': (25.276987, 55.296249),
          'Los Angeles': (34.052235, -118.243683),
          'Singapore': (1.290270, 103.851959),
          'Mumbai': (19.076090, 72.877426),
          'Cairo': (30.033333, 31.233334),
          'Mexico City': (19.432608, -99.133209)}

month_to_season = {12: "winter", 1: "winter", 2: "winter",
                   3: "spring", 4: "spring", 5: "spring",
                   6: "summer", 7: "summer", 8: "summer",
                   9: "autumn", 10: "autumn", 11: "autumn"}



def temperature_plot_1(city, plot_data, data):
    years = pd.unique(plot_data['timestamp'].dt.year)
    
    for year in years:
        year_data = plot_data[(plot_data['city'] == city) & (plot_data['timestamp'].dt.year == year)]
        
        highlight = year_data[year_data.apply(lambda row: is_anomaly(city, row['temperature'], row['season'], data), axis=1)]
        
        # Построение графика
        fig = px.line(year_data, x='timestamp', y=['temperature', 'smoothed_temperature'],
                      title=f'{city} {year}')
        
        # Выделение точек с аномальной температурой
        fig.add_scatter(x=highlight['timestamp'], y=highlight['temperature'], 
                        mode='markers', marker=dict(color='red', size=10, symbol='circle'),
                        name=f'Anomaly temperature')
        
        fig.update_layout(title=f'{city} {year}', xaxis_title='Date', yaxis_title='Temperature (°C)')
        st.plotly_chart(fig)
        
def temperature_plot_2(city, plot_data):
    city_data = plot_data[plot_data['city'] == city].copy()
    city_data['year'] = city_data['timestamp'].dt.year
    city_data['day_of_year'] = city_data['timestamp'].dt.dayofyear

    fig = px.line(city_data, x='day_of_year', y='smoothed_temperature', color='year', title=f'Temperature dynamics in {city}')
    
    fig.update_layout(
        xaxis_title='Day of Year',
        yaxis_title='Temperature (°C)',
        template='plotly_white'
    )
    
    st.plotly_chart(fig)

def current_season():
    '''
    Определяет текущий сезон.
    '''
    return month_to_season[datetime.now().month]

def is_anomaly(city, temp, season, data):
    '''
    Определяет аномальная температура или нет.
    '''
    mean, std = data[(data['city'] == city) & (data['season'] == season)][['mean_temperature', 'std_temperature']].head(1).values[0]
    
    if temp > mean + 2 * std or temp < mean - 2 * std:
        return True
    return False 

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
        st.write(f"An error occurred while retrieving the data")
        
        return {}

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

def temperature_SMA(data):
    data_copy = data.copy()
    for city in pd.unique(data_copy['city']):
        sorted_data = data_copy[data_copy['city'] == city].sort_values('timestamp')
        smoothed_temperature = SMA(sorted_data, 30)
        data_copy.loc[smoothed_temperature.index, 'smoothed_temperature'] = smoothed_temperature
    return data_copy

@st.cache_data
def get_results(data, city, key):
    '''
    Рассчет и вывод результатов.
    '''
    data['timestamp'] = pd.to_datetime(data['timestamp']).dt.normalize()
    data = temperature_SMA(data)
    data['mean_temperature'] = data.groupby(['city', 'season'])['smoothed_temperature'].transform('mean')
    data['std_temperature'] = data.groupby(['city', 'season'])['smoothed_temperature'].transform('std')
    
    cur_temp = get_weather(*cities[city], key)
    anomaly = is_anomaly(city, cur_temp, current_season(), data)
    
    if anomaly:
        st.write(f'Current weather in {city}: {cur_temp} °C, is anomalous for the season')
    else:
        st.write(f"Current weather in {city}: {cur_temp} °C")
    
    st.write(pd.pivot_table(data=data[data['city'] == city],
                            values='smoothed_temperature',
                            index='season', aggfunc=['mean', 'std']))
    
    plot_data = None

    for city_ in pd.unique(data['city']):
        plot_data = pd.concat([plot_data, data[data['city'] == city_].iloc[29:]])
    
    temperature_plot_2(city, plot_data)
    temperature_plot_1(city, plot_data, data)

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
    
    return True

@st.cache_data
def unique_city(data):
    '''
    Возвращает массив городов из датасета.
    '''
    return data['city'].unique()

@st.cache_data
def load_data(uploaded_file):
    '''
    Загрузка файла.
    '''
    return pd.read_csv(uploaded_file)

def upload_data(checkbox=None):
    '''
    Загрузка датасета.
    '''
    data = None
    
    if checkbox:
        uploaded_file = st.file_uploader("Select a file")
        
        if uploaded_file is not None:
            data = load_data(uploaded_file) 
    else:
        data = load_data('temperature_data.csv')
    
    return data

def main():
    st.title('City temperature analysis')

    agree = st.checkbox('Upload your data')

    data = upload_data(agree)

    if data is not None:
        st.write(data)
        
        city = st.selectbox('Select a city', unique_city(data))
        
        key = st.text_input('OpenWeatherMap API', placeholder='Enter your key')

        if check_status(key):
            results = st.checkbox('Show results')
            
            if results:
                with st.spinner("Calculation in progress..."):
                    get_results(data, city, key)
   
   
         
main()