#!/usr/bin/env python

import os
import cgi
import logging
import oauth2 as oauth
from flask import Flask, render_template, abort, request, session, redirect, url_for, flash
from tasks import scrape_gmail_messages


# Flask application
config_class_name = 'Development' if __name__ == '__main__' else 'Production'
app = Flask(__name__)
app.config.from_object('config.%sConfig' % config_class_name)
app.secret_key = app.config['APP_SECRET_KEY']
# Init logging
log_file = os.path.join(os.path.dirname(__file__), app.config['LOG_FILE']) if app.config['LOG_FILE'] else None
log_level = app.config['LOG_LEVEL']
if log_file and log_level:
    if not os.path.exists(log_file):
        logdir = os.path.dirname(log_file)
        if not os.path.exists(logdir):
            os.makedirs(logdir)
        open(log_file, 'w').close()
if log_level:
    logging.basicConfig(filename=log_file, format='%(message)s', level=log_level)
# Init OAuth
consumer = oauth.Consumer(app.config['GOOGLE_KEY'], app.config['GOOGLE_SECRET'])
client = oauth.Client(consumer)


# Views
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login')
def login():
    resp, content = client.request(app.config['OAUTH_REQUEST_TOKEN_URL'])
    if resp['status'] != '200':
        abort(502, 'Invalid response from Google.')
    session['request_token'] = dict(cgi.parse_qsl(content))
    return redirect('%s?oauth_token=%s&oauth_callback=http://%s%s'
        % (app.config['OAUTH_AUTHORIZATION_URL'], session['request_token']['oauth_token'], request.host, url_for('oauth_authorized')))


@app.route('/oauth-authorized')
def oauth_authorized():
    token = oauth.Token(session['request_token']['oauth_token'], session['request_token']['oauth_token_secret'])
    client = oauth.Client(consumer, token)
    resp, content = client.request(app.config['OAUTH_ACCESS_TOKEN_URL'])
    # TODO: Handle 'Deny access' (status 400)
    if resp['status'] != '200':
        # TODO: Show better error
        abort(502, 'Invalid response from Google.')
    session['access_token'] = dict(cgi.parse_qsl(content))
    return redirect(url_for('scraper'))


@app.route('/scraper')
def scraper():
    access_oauth_token, access_oauth_token_secret = session['access_token']['oauth_token'], session['access_token']['oauth_token_secret']
    consumer_key, consumer_secret = app.config['GOOGLE_KEY'], app.config['GOOGLE_SECRET']
    result = scrape_gmail_messages.delay(access_oauth_token, access_oauth_token_secret, consumer_key, consumer_secret   )
    # TODO: return render_template('processing.html')
    phone_numbers = result.get()
    return render_template('results.html', phone_numbers=phone_numbers)
        

# Error handlers
@app.errorhandler(404)
def page_not_found(message = None):
    return render_template('error404.html'), 404


@app.errorhandler(500)
@app.route('/internal_error.html')
def internal_error(message = None):
    return render_template('error500.html'), 500


# Run dev server
if __name__ == '__main__':
    app.run(app.config['DEV_HOST'], port=app.config['DEV_PORT'], debug=app.config['DEBUG'])
