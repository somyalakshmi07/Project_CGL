from flask import Flask, render_template
from app import app1_blueprint
from app1 import app2_blueprint
from app2 import app3_blueprint

app = Flask(__name__)

# Register each blueprint
app.register_blueprint(app1_blueprint, url_prefix='/app')
app.register_blueprint(app2_blueprint, url_prefix='/app1')
app.register_blueprint(app3_blueprint, url_prefix='/app2')

# This route will load home.html when you open http://localhost:5000
@app.route('/')
def index():
    return render_template('home.html')  # Make sure this file exists in /templates

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/production')
def production():
    return render_template('production.html')

@app.route('/productivity')
def productivity():
    return render_template('productivity.html')

@app.route('/order_punch')
def order_punch():
    return render_template('order_punch.html')


if __name__ == '__main__':
    app.run(debug=True)
