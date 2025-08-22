from flask import Flask, request, render_template_string
import requests
import os

app = Flask(__name__)

API_KEY = os.getenv('NEW_RELIC_API_KEY')
ACCOUNT_ID = os.getenv('NEW_RELIC_ACCOUNT_ID')

HTML = """
<!doctype html>
<html>
<head>
    <title>Consulta New Relic</title>
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
        input[type="text"] {
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
        .not-found {
            color: red;
            font-weight: bold;
        }
    </style>
</head>
<body>
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

    return render_template_string(HTML, results=results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
