from flask import Flask, render_template, request

app = Flask(__name__, static_url_path='/static', static_folder='static')
