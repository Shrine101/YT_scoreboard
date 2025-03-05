from flask import Flask
from flask import render_template, jsonify

app = Flask(__name__)



@app.route('/data_json')
def data_json():
    dummy_data = [
        # Player total scores (starting with 501 each)
        {
            "id": 1,
            "player_name": "Player 1",
            "total_score": 501,
            "row_type": "player_score"
        },
        {
            "id": 2,
            "player_name": "Player 2",
            "total_score": 501,
            "row_type": "player_score"
        },
        {
            "id": 3,
            "player_name": "Player 3",
            "total_score": 501,
            "row_type": "player_score"
        },
        {
            "id": 4,
            "player_name": "Player 4",
            "total_score": 501,
            "row_type": "player_score"
        },
        # Turn details for each player
        {
            "id": 5,
            "player_name": "Player 1",
            "turn_number": 1,
            "first_throw": 60,
            "second_throw": 60, 
            "third_throw": 60,
            "row_type": "turn"
        },
        {
            "id": 6,
            "player_name": "Player 2",
            "turn_number": 1,
            "first_throw": 45,
            "second_throw": 26, 
            "third_throw": 40,
            "row_type": "turn"
        },
        {
            "id": 7,
            "player_name": "Player 3",
            "turn_number": 1,
            "first_throw": 60,
            "second_throw": 57, 
            "third_throw": 24,
            "row_type": "turn"
        },
        {
            "id": 8,
            "player_name": "Player 4",
            "turn_number": 1,
            "first_throw": 41,
            "second_throw": 60, 
            "third_throw": 38,
            "row_type": "turn"
        }
    ]
    return jsonify(dummy_data)
    

@app.route('/')
def index():
    dummy_data = data_json()

    return render_template(
        'index.html',
        matches=dummy_data.json
        
    )