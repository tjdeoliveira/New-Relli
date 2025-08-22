from flask import Flask, request, render_template_string
import requests
import os
import csv
from datetime import datetime, timezone, timedelta
import io

app = Flask(__name__)

API_KEY = os.getenv('NEW_RELIC_API_KEY')
ACCOUNT_ID = os.getenv('NEW_RELIC_ACCOUNT_ID')
MAX_RESULTS = 5000  # Limite máximo de resultados por consulta NRQL
MIN_INTERVAL = timedelta(minutes=1)  # Intervalo mínimo para evitar recursão infinita

def parse_brazilian_datetime(date_str):
    """Parse a Brazilian datetime string (DD/MM/YYYY HH:MM:SS) to UTC datetime."""
    try:
        dt_br = datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')
        tz_br = timezone(timedelta(hours=-3))
        dt_br = dt_br.replace(tzinfo=tz_br)
        dt_utc = dt_br.astimezone(timezone.utc)
        return dt_utc
    except ValueError as e:
        return None, f"Erro ao parsear data: {e}. Use o formato DD/MM/YYYY HH:MM:SS."

def fetch_newrelic_data(start_time, end_time, company_id):
    """Fetch data from New Relic for a given time range and company ID."""
    nrql_query = (
        "SELECT * "
        "FROM Log "
        "WHERE (type = 'SENT_MESSAGE_STATUS' OR type = 'SENT_MESSAGE' OR type = 'SENT_ALL_MESSAGE') "
        f"AND (status.code IN ('failed') AND company.id IN ('{company_id}')) "
        f"SINCE '{start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC' "
        f"UNTIL '{end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC' "
        "LIMIT MAX "
        "ORDER BY timestamp ASC"
    )
    payload = {
        "query": f"""{{
          actor {{
            account(id: {ACCOUNT_ID}) {{
              nrql(query: "{nrql_query}") {{
                results
              }}
            }}
          }}
        }}"""
    }
    response = requests.post(
        "https://api.newrelic.com/graphql",
        headers={
            "API-Key": API_KEY,
            "Content-Type": "application/json"
        },
        json=payload
    )
    if response.status_code == 200:
        data = response.json()
        results = data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
        return results, None
    else:
        return [], f"Erro na requisição: {response.text}"

def fetch_recursive(start_time, end_time, company_id):
    """Recursive fetch with intelligent subdivision if limit is exceeded."""
    if end_time - start_time <= MIN_INTERVAL:
        return fetch_newrelic_data(start_time, end_time, company_id)

    results, error = fetch_newrelic_data(start_time, end_time, company_id)
    if error:
        return results, error
    if len(results) < MAX_RESULTS:
        return results, None
    else:
        mid_time = start_time + (end_time - start_time) / 2
        left_results, left_error = fetch_recursive(start_time, mid_time, company_id)
        if left_error:
            return left_results, left_error
        right_results, right_error = fetch_recursive(mid_time, end_time, company_id)
        if right_error:
            return right_results, right_error
        return left_results + right_results, None

HTML_MESSAGE_ID = """
<!doctype html>
<html>
<head>
    <title>Consulta New Relic - Message ID</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f6f8;
            padding: 30px;
            color: #333;
        }
        h2 {
            color: #0066cc;
        }
        form {
            margin-bottom: 20px;
        }
        input[type="text"], input[type="datetime-local"] {
            padding: 8px;
            width: 300px;
            border: 1px solid #ccc;
            border-radius: 5px;
        }
        input[type="submit"] {
            padding: 8px 15px;
            background-color: #0066cc;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        ul {
            list-style: none;
            padding: 0;
        }
        li {
            background-color: white;
            padding: 15px;
            border: 1px solid #ddd;
            margin-bottom: 10px;
            border-radius: 8px;
        }
        .not-found, .error {
            color: red;
            font-weight: bold;
        }
        .nav {
            margin-bottom: 20px;
        }
        .nav a {
            margin-right: 10px;
            color: #0066cc;
            text-decoration: none;
        }
        .nav a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">Consulta por Message ID</a>
        <a href="/csv-download">Consulta por Período e Company ID</a>
    </div>
    <h2>Consulta de message.id no New Relic</h2>
    <form method="post">
        <input name="message_id" type="text" placeholder="Digite o message.id" required>
        <input type="submit" value="Buscar">
    </form>

    {% if results is not none %}
        {% if results|length == 0 %}
            <p class="not-found">message.id não encontrado.</p>
        {% else %}
            <h3>Resultados:</h3>
            <ul>
            {% for item in results %}
                <li>
                    <strong>chat.id:</strong> {{ item['chat.id'] }}<br>
                    <strong>status.code:</strong> {{ item['status.code'] }}<br>
                    <strong>status.description:</strong> {{ item['status.description'] }}<br>
                </li>
            {% endfor %}
            </ul>
        {% endif %}
    {% endif %}
</body>
</html>
"""

HTML_CSV_DOWNLOAD = """
<!doctype html>
<html>
<head>
    <title>Consulta New Relic - CSV Download</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f6f8;
            padding: 30px;
            color: #333;
        }
        h2 {
            color: #0066cc;
        }
        form {
            margin-bottom: 20px;
        }
        input[type="text"], input[type="datetime-local"] {
            padding: 8px;
            width: 300px;
            border: 1px solid #ccc;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        input[type="submit"] {
            padding: 8px 15px;
            background-color: #0066cc;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        .error, .not-found {
            color: red;
            font-weight: bold;
        }
        .nav {
            margin-bottom: 20px;
        }
        .nav a {
            margin-right: 10px;
            color: #0066cc;
            text-decoration: none;
        }
        .nav a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/">Consulta por Message ID</a>
        <a href="/csv-download">Consulta por Período e Company ID</a>
    </div>
    <h2>Consulta por Período e Company ID</h2>
    <form method="post">
        <label>Data e hora de início (máximo 24h de intervalo):</label><br>
        <input name="start_date" type="datetime-local" required><br>
        <label>Data e hora de término:</label><br>
        <input name="end_date" type="datetime-local" required><br>
        <label>Company ID:</label><br>
        <input name="company_id" type="text" placeholder="Digite o company.id" required><br>
        <input type="submit" value="Gerar CSV">
    </form>

    {% if error %}
        <p class="error">{{ error }}</p>
    {% endif %}
    {% if results is not none %}
        {% if results|length == 0 %}
            <p class="not-found">Nenhum resultado encontrado no intervalo especificado.</p>
        {% endif %}
    {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    if request.method == 'POST':
        message_id = request.form['message_id']
        query = {
            "query": f"""{{
              actor {{
                account(id: {ACCOUNT_ID}) {{
                  nrql(query: "SELECT chat.id, status.code, status.description FROM Log WHERE (type = 'SENT_MESSAGE_STATUS' OR type = 'SENT_MESSAGE' OR type = 'SENT_ALL_MESSAGE') AND message.id IN ({message_id}) SINCE 1 month ago UNTIL now") {{
                    results
                  }}
                }}
              }}
            }}"""
        }
        response = requests.post(
            "https://api.newrelic.com/graphql",
            headers={
                "API-Key": API_KEY,
                "Content-Type": "application/json"
            },
            json=query
        )
        if response.status_code == 200:
            data = response.json()
            results = data["data"]["actor"]["account"]["nrql"]["results"]
        else:
            results = []
    return render_template_string(HTML_MESSAGE_ID, results=results)

@app.route('/csv-download', methods=['GET', 'POST'])
def csv_download():
    error = None
    results = None
    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        company_id = request.form.get('company_id')

        # Validar company_id
        if not company_id or not company_id.strip():
            error = "Company ID não pode ser vazio."
            return render_template_string(HTML_CSV_DOWNLOAD, error=error, results=results)

        # Converter datas de entrada
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
            tz_br = timezone(timedelta(hours=-3))
            start_date = start_date.replace(tzinfo=tz_br).astimezone(timezone.utc)
            end_date = end_date.replace(tzinfo=tz_br).astimezone(timezone.utc)
        except ValueError:
            error = "Formato de data inválido. Use o formato fornecido pelo campo de data."
            return render_template_string(HTML_CSV_DOWNLOAD, error=error, results=results)

        # Validar intervalo de 24 horas
        if end_date - start_date > timedelta(hours=24):
            error = "O intervalo entre as datas não pode exceder 24 horas."
            return render_template_string(HTML_CSV_DOWNLOAD, error=error, results=results)

        # Coletar resultados
        results, fetch_error = fetch_recursive(start_date, end_date, company_id)
        if fetch_error:
            error = fetch_error
            return render_template_string(HTML_CSV_DOWNLOAD, error=error, results=results)

        if results:
            # Ordenar resultados por timestamp
            results.sort(key=lambda r: int(r.get("timestamp", 0)))

            # Gerar CSV
            output = io.StringIO()
            writer = csv.writer(output, delimiter=';')
            writer.writerow(["timestamp", "chat.id", "status.description", "company.id"])
            tz_br = timezone(timedelta(hours=-3))
            for r in results:
                timestamp_ms = r.get("timestamp", "")
                chat_id = r.get("chat.id", "")
                status_desc = r.get("status.description", "")
                if timestamp_ms:
                    try:
                        timestamp_sec = int(timestamp_ms) / 1000
                        dt_utc = datetime.fromtimestamp(timestamp_sec, tz=timezone.utc)
                        dt_br = dt_utc.astimezone(tz_br)
                        timestamp_str = dt_br.strftime('%d/%m/%Y %H:%M:%S')
                    except ValueError:
                        timestamp_str = timestamp_ms
                else:
                    timestamp_str = ""
                writer.writerow([timestamp_str, chat_id, status_desc, company_id])

            # Preparar resposta para download
            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment;filename=resultados.csv"}
            )

    return render_template_string(HTML_CSV_DOWNLOAD, error=error, results=results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

