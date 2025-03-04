from flask import Flask
from flask import render_template

app = Flask(__name__)


@app.route('/')
def index():
    dummy_data = [
        {
            "id": 1,
            "starting_time": "16:00",
            "team_a": "Random Team 1",
            "score": "0 - 0",
            "team_b": "Random Team 2",
            "minute": "00:00",
        },
        {
            "id": 2,
            "starting_time": "18:00",
            "team_a": "Random Team 3",
            "score": "0 - 0",
            "team_b": "Random Team 4",
            "minute": "00:00",
        },
    ]
    return render_template(
        'index.html',
        matches=dummy_data
        
    )