from flask import Flask, request, render_template_string
import requests
import os

app = Flask(__name__)

API_KEY = os.getenv('NRAK-75C6I503C080UJ60CA73CH1XBTT')
ACCOUNT_ID = os.getenv('1896682')

HTML = """
<!doctype html>
<title>Consulta New Relic</title>
<h2>Buscar message.id no New Relic</h2>
<form method="post">
  <input name="message_id" placeholder="Digite o message.id" required>
  <input type="submit" value="Buscar">
</form>
{% if results %}
  <h3>Resultados:</h3>
  <ul>
    {% for item in results %}
      <li>
        <strong>chat.id:</strong> {{ item['chat.id'] }}<br>
        <strong>status.code:</strong> {{ item['status.code'] }}<br>
        <strong>status.description:</strong> {{ item['status.description'] }}<br><br>
      </li>
    {% endfor %}
  </ul>
{% endif %}
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
                  nrql(query: "SELECT chat.id, status.code, status.description FROM Log WHERE (type = 'SENT_MESSAGE_STATUS' OR type = 'SENT_MESSAGE' OR type = 'SENT_ALL_MESSAGE') AND message.id IN ({message_id}) SINCE 7 days ago UNTIL now") {{
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
            results = [{"chat.id": "Erro", "status.code": response.status_code, "status.description": response.text}]

    return render_template_string(HTML, results=results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
