# Importa as bibliotecas necessárias
import dash  # Biblioteca para criar aplicações web interativas
from dash import dcc, html  # Componentes de Dash para criar a interface gráfica
from dash.dependencies import Input, Output, State  # Gerencia interações e estados no Dash
import plotly.graph_objs as go  # Biblioteca para criar gráficos interativos
import requests  # Biblioteca para realizar requisições HTTP
from datetime import datetime  # Para manipular datas e horários
import pytz  # Para trabalhar com fusos horários

# Configuração do endereço IP e porta do servidor que armazena os dados dos sensores
IP_ADDRESS = "52.137.83.133"  # Endereço IP do servidor
PORT_STH = 8666  # Porta do serviço STH-Comet
DASH_HOST = "0.0.0.0"  # Define o host como acessível de qualquer IP

# FUNÇÃO PARA PEGAR OS ATRIBUTOS DE QUALQUER SENSOR
def get_sensor_data(entity_type, entity_id, attribute, lastN):
    """
    Busca os últimos 'lastN' valores de um atributo de uma entidade específica.

    Parâmetros:
    - entity_type: Tipo da entidade (ex: 'Lamp', 'DHTSensor').
    - entity_id: ID único da entidade.
    - attribute: Nome do atributo (ex: 'luminosity').
    - lastN: Quantidade de valores recentes a buscar.

    Retorna:
    - Lista de valores do atributo ou uma lista vazia em caso de erro.
    """
    # URL para acessar os dados do sensor via API do STH-Comet
    url = f"http://{IP_ADDRESS}:{PORT_STH}/STH/v1/contextEntities/type/{entity_type}/id/{entity_id}/attributes/{attribute}?lastN={lastN}"

    # Cabeçalhos para FIWARE
    headers = {
        'fiware-service': 'smart',
        'fiware-servicepath': '/'
    }

    # Faz a requisição GET para a API
    response = requests.get(url, headers=headers)

    if response.status_code == 200:  # Verifica se a requisição foi bem-sucedida
        data = response.json()
        try:
            # Extrai os valores do atributo do JSON retornado
            values = data['contextResponses'][0]['contextElement']['attributes'][0]['values']
            return values
        except KeyError as e:
            # Trata erros caso a estrutura esperada do JSON esteja ausente
            print(f"Key error: {e}")
            return []
    else:
        # Exibe mensagem de erro em caso de falha na requisição
        print(f"Error accessing {url}: {response.status_code}")
        return []

# FUNÇÃO PARA CONVERTER TIMESTAMPS UTC PARA O HORÁRIO DE SÃO PAULO
def convert_to_sao_paulo_time(timestamps):
    """
    Converte uma lista de timestamps UTC para o fuso horário de São Paulo.

    Parâmetros:
    - timestamps: Lista de strings de timestamps no formato ISO.

    Retorna:
    - Lista de objetos datetime ajustados para o fuso horário de São Paulo.
    """
    utc = pytz.utc  # Define o fuso horário UTC
    sp = pytz.timezone('America/Sao_Paulo')  # Define o fuso horário de São Paulo
    converted_timestamps = []  # Lista para armazenar os timestamps convertidos

    for timestamp in timestamps:
        try:
            # Remove caracteres extras e converte para datetime
            timestamp = timestamp.replace('T', ' ').replace('Z', '')
            converted_time = utc.localize(datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f')).astimezone(sp)
        except ValueError:
            # Trata timestamps sem milissegundos
            converted_time = utc.localize(datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')).astimezone(sp)

        converted_timestamps.append(converted_time)

    return converted_timestamps

# Instância da aplicação Dash
app = dash.Dash(__name__)

# Layout da aplicação com divisões para cada sensor
app.layout = html.Div([
    html.H1('Dashboard dos sensores LDR, DHT22 e Voltímetro'),  # Título principal

    # Seção do gráfico de luminosidade
    html.Div([
        html.H2('Luminosidade'),
        dcc.Graph(id='luminosity-graph'),  # Gráfico
        dcc.Store(id='luminosity-data-store', data={'timestamps': [], 'luminosity_values': []}),  # Armazena dados localmente
    ]),

    # Seção do gráfico de umidade
    html.Div([
        html.H2('Umidade'),
        dcc.Graph(id='humidity-graph'),
        dcc.Store(id='humidity-data-store', data={'timestamps': [], 'humidity_values': []}),
    ]),

    # Seção do gráfico de temperatura
    html.Div([
        html.H2('Temperatura'),
        dcc.Graph(id='temperature-graph'),
        dcc.Store(id='temperature-data-store', data={'timestamps': [], 'temperature_values': []}),
    ]),

    # Seção do gráfico de tensão do potenciômetro
    html.Div([
        html.H2('Medição da Tensão'),
        dcc.Graph(id='potentiometer-graph'),
        dcc.Store(id='potentiometer-data-store', data={'timestamps': [], 'potentiometer_values': []}),
    ]),

    # Intervalo para atualizações automáticas a cada 10 segundos
    dcc.Interval(
        id='interval-component',
        interval=10 * 1000,  # Intervalo em milissegundos
        n_intervals=0  # Contador de intervalos
    )
])
# Callback para atualizar os dados armazenados localmente de cada sensor
@app.callback(
    [Output('luminosity-data-store', 'data'),  # Saída: dados de luminosidade
     Output('humidity-data-store', 'data'),  # Saída: dados de umidade
     Output('temperature-data-store', 'data'),  # Saída: dados de temperatura
     Output('potentiometer-data-store', 'data')],  # Saída: dados de tensão do potenciômetro
    Input('interval-component', 'n_intervals'),  # Entrada: número de intervalos do componente de atualização automática
    State('luminosity-data-store', 'data'),  # Estado: dados armazenados de luminosidade
    State('humidity-data-store', 'data'),  # Estado: dados armazenados de umidade
    State('temperature-data-store', 'data'),  # Estado: dados armazenados de temperatura
    State('potentiometer-data-store', 'data')  # Estado: dados armazenados de tensão
)
def update_data_store(n, stored_luminosity, stored_humidity, stored_temperature, stored_potentiometer):
    """
    Atualiza os dados armazenados localmente para cada sensor a partir da API.

    Parâmetros:
    - n: Número de atualizações realizadas.
    - stored_luminosity, stored_humidity, stored_temperature, stored_potentiometer:
      Dados atualmente armazenados de cada sensor.

    Retorna:
    - Os dados atualizados para cada sensor.
    """
    # Atualiza os dados de luminosidade
    data_luminosity = get_sensor_data('Lamp', 'urn:ngsi-ld:Lamp:003', 'luminosity', 10)
    if data_luminosity:
        luminosity_values = [float(entry['attrValue']) for entry in data_luminosity]  # Extrai os valores
        timestamps_luminosity = [entry['recvTime'] for entry in data_luminosity]  # Extrai os timestamps
        timestamps_luminosity = convert_to_sao_paulo_time(timestamps_luminosity)  # Converte os timestamps
        stored_luminosity['timestamps'].extend(timestamps_luminosity)  # Atualiza os dados armazenados
        stored_luminosity['luminosity_values'].extend(luminosity_values)

    # Atualiza os dados de umidade
    data_humidity = get_sensor_data('DHTSensor', 'urn:ngsi-ld:DHT:001', 'humidity', lastN=10)
    if data_humidity:
        humidity_values = [float(entry['attrValue']) for entry in data_humidity]
        timestamps_humidity = [entry['recvTime'] for entry in data_humidity]
        timestamps_humidity = convert_to_sao_paulo_time(timestamps_humidity)
        stored_humidity['timestamps'].extend(timestamps_humidity)
        stored_humidity['humidity_values'].extend(humidity_values)

    # Atualiza os dados de temperatura
    data_temperature = get_sensor_data('DHTSensor', 'urn:ngsi-ld:DHT:001', 'temperature', lastN=10)
    if data_temperature:
        temperature_values = [float(entry['attrValue']) for entry in data_temperature]
        timestamps_temperature = [entry['recvTime'] for entry in data_temperature]
        timestamps_temperature = convert_to_sao_paulo_time(timestamps_temperature)
        stored_temperature['timestamps'].extend(timestamps_temperature)
        stored_temperature['temperature_values'].extend(temperature_values)

    # Atualiza os dados de tensão do potenciômetro
    data_potentiometer = get_sensor_data('Potenciometer', 'urn:ngsi-ld:POT:001', 'voltage', lastN=10)
    if data_potentiometer:
        potentiometer_values = [float(entry['attrValue']) for entry in data_potentiometer]
        timestamps_potentiometer = [entry['recvTime'] for entry in data_potentiometer]
        timestamps_potentiometer = convert_to_sao_paulo_time(timestamps_potentiometer)
        stored_potentiometer['timestamps'].extend(timestamps_potentiometer)
        stored_potentiometer['potentiometer_values'].extend(potentiometer_values)

    return stored_luminosity, stored_humidity, stored_temperature, stored_potentiometer  # Retorna os dados atualizados


# Callback para atualizar o gráfico de potenciômetro
@app.callback(
    Output('potentiometer-graph', 'figure'),  # Saída: gráfico do potenciômetro
    Input('potentiometer-data-store', 'data')  # Entrada: dados armazenados do potenciômetro
)
def update_potentiometer_graph(stored_potentiometer):
    """
    Atualiza o gráfico de tensão do potenciômetro.

    Parâmetros:
    - stored_potentiometer: Dados armazenados localmente do potenciômetro.

    Retorna:
    - Um objeto Figure contendo o gráfico atualizado.
    """
    if stored_potentiometer['timestamps'] and stored_potentiometer['potentiometer_values']:
        # Calcula a média dos valores
        mean_potentiometer = sum(stored_potentiometer['potentiometer_values']) / len(stored_potentiometer['potentiometer_values'])

        # Cria o trace principal do gráfico
        trace_potentiometer = go.Scatter(
            x=stored_potentiometer['timestamps'],
            y=stored_potentiometer['potentiometer_values'],
            mode='lines+markers',  # Linhas e marcadores
            name='Tensao',
            line=dict(color='purple')  # Cor da linha
        )

        # Cria uma linha indicando a média
        trace_mean = go.Scatter(
            x=[stored_potentiometer['timestamps'][0], stored_potentiometer['timestamps'][-1]],  # Linhas horizontais
            y=[mean_potentiometer, mean_potentiometer],
            mode='lines',
            name='Media da Tensao',
            line=dict(color='blue', dash='dash')  # Linha tracejada
        )

        # Combina os traces em uma figura
        fig_potentiometer = go.Figure(data=[trace_potentiometer, trace_mean])
        fig_potentiometer.update_layout(
            title='Tensao pelo Tempo',
            xaxis_title='Timestamp',
            yaxis_title='Potentiometer',
            hovermode='closest'  # Modo de hover
        )

        return fig_potentiometer  # Retorna o gráfico

    return {}  # Retorna um gráfico vazio se não houver dados
# Callback para atualizar o gráfico de luminosidade
@app.callback(
    Output('luminosity-graph', 'figure'),  # Saída: gráfico de luminosidade
    Input('luminosity-data-store', 'data')  # Entrada: dados armazenados de luminosidade
)
def update_luminosity_graph(stored_luminosity):
    """
    Atualiza o gráfico de luminosidade.

    Parâmetros:
    - stored_luminosity: Dados armazenados localmente de luminosidade.

    Retorna:
    - Um objeto Figure contendo o gráfico atualizado.
    """
    if stored_luminosity['timestamps'] and stored_luminosity['luminosity_values']:
        # Calcula a média dos valores de luminosidade
        mean_luminosity = sum(stored_luminosity['luminosity_values']) / len(stored_luminosity['luminosity_values'])

        # Cria o trace principal do gráfico
        trace_luminosity = go.Scatter(
            x=stored_luminosity['timestamps'],
            y=stored_luminosity['luminosity_values'],
            mode='lines+markers',
            name='Luminosity',
            line=dict(color='red')  # Define a cor da linha como vermelha
        )

        # Cria uma linha indicando a média
        trace_mean = go.Scatter(
            x=[stored_luminosity['timestamps'][0], stored_luminosity['timestamps'][-1]],
            y=[mean_luminosity, mean_luminosity],
            mode='lines',
            name='Mean Luminosity',
            line=dict(color='blue', dash='dash')  # Linha tracejada azul
        )

        # Combina os traces em uma figura
        fig_luminosity = go.Figure(data=[trace_luminosity, trace_mean])
        fig_luminosity.update_layout(
            title='Luminosity Over Time',
            xaxis_title='Timestamp',
            yaxis_title='Luminosity',
            hovermode='closest'
        )

        return fig_luminosity  # Retorna o gráfico atualizado

    return {}  # Retorna um gráfico vazio se não houver dados


# Callback para atualizar o gráfico de umidade
@app.callback(
    Output('humidity-graph', 'figure'),  # Saída: gráfico de umidade
    Input('humidity-data-store', 'data')  # Entrada: dados armazenados de umidade
)
def update_humidity_graph(stored_humidity):
    """
    Atualiza o gráfico de umidade.

    Parâmetros:
    - stored_humidity: Dados armazenados localmente de umidade.

    Retorna:
    - Um objeto Figure contendo o gráfico atualizado.
    """
    if stored_humidity['timestamps'] and stored_humidity['humidity_values']:
        # Calcula a média dos valores de umidade
        mean_humidity = sum(stored_humidity['humidity_values']) / len(stored_humidity['humidity_values'])

        # Cria o trace principal do gráfico
        trace_humidity = go.Scatter(
            x=stored_humidity['timestamps'],
            y=stored_humidity['humidity_values'],
            mode='lines+markers',
            name='Humidity',
            line=dict(color='green')  # Define a cor da linha como verde
        )

        # Cria uma linha indicando a média
        trace_mean = go.Scatter(
            x=[stored_humidity['timestamps'][0], stored_humidity['timestamps'][-1]],
            y=[mean_humidity, mean_humidity],
            mode='lines',
            name='Mean Humidity',
            line=dict(color='blue', dash='dash')  # Linha tracejada azul
        )

        # Combina os traces em uma figura
        fig_humidity = go.Figure(data=[trace_humidity, trace_mean])
        fig_humidity.update_layout(
            title='Humidity Over Time',
            xaxis_title='Timestamp',
            yaxis_title='Humidity',
            hovermode='closest'
        )

        return fig_humidity  # Retorna o gráfico atualizado

    return {}  # Retorna um gráfico vazio se não houver dados


# Callback para atualizar o gráfico de temperatura
@app.callback(
    Output('temperature-graph', 'figure'),  # Saída: gráfico de temperatura
    Input('temperature-data-store', 'data')  # Entrada: dados armazenados de temperatura
)
def update_temperature_graph(stored_temperature):
    """
    Atualiza o gráfico de temperatura.

    Parâmetros:
    - stored_temperature: Dados armazenados localmente de temperatura.

    Retorna:
    - Um objeto Figure contendo o gráfico atualizado.
    """
    if stored_temperature['timestamps'] and stored_temperature['temperature_values']:
        # Calcula a média dos valores de temperatura
        mean_temperature = sum(stored_temperature['temperature_values']) / len(stored_temperature['temperature_values'])

        # Cria o trace principal do gráfico
        trace_temperature = go.Scatter(
            x=stored_temperature['timestamps'],
            y=stored_temperature['temperature_values'],
            mode='lines+markers',
            name='Temperature',
            line=dict(color='orange')  # Define a cor da linha como laranja
        )

        # Cria uma linha indicando a média
        trace_mean = go.Scatter(
            x=[stored_temperature['timestamps'][0], stored_temperature['timestamps'][-1]],
            y=[mean_temperature, mean_temperature],
            mode='lines',
            name='Mean Temperature',
            line=dict(color='blue', dash='dash')  # Linha tracejada azul
        )

        # Combina os traces em uma figura
        fig_temperature = go.Figure(data=[trace_temperature, trace_mean])
        fig_temperature.update_layout(
            title='Temperature Over Time',
            xaxis_title='Timestamp',
            yaxis_title='Temperature',
            hovermode='closest'
        )

        return fig_temperature  # Retorna o gráfico atualizado

    return {}  # Retorna um gráfico vazio se não houver dados


# Inicia o servidor Dash
if __name__ == '__main__':
    """
    Ponto de entrada principal do script. 
    Inicia o servidor Dash na porta 8050 e permite depuração.
    """
    app.run_server(debug=True, host=DASH_HOST, port=8050)
