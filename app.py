from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_babelex import format_datetime
import pytz 
import os
from flask import Flask, render_template
from flask_babelex import format_datetime
from flask_bootstrap import Bootstrap
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse
from collections import OrderedDict
import logging
import math

load_dotenv()
app = Flask(__name__, template_folder='templates')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://")
db = SQLAlchemy(app)
Bootstrap(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    total_engagement = db.Column(db.Integer, default=0)
class Tweet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('tweets', lazy=True))
    content = db.Column(db.String(280))
    likes = db.Column(db.Integer)
    retweets = db.Column(db.Integer)
    replies = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
class FetchTime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref=db.backref('fetch_times', lazy=True))
    last_fetched = db.Column(db.DateTime)
    tweet_increase = db.Column(db.Integer)
class TotalIncrease(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime(timezone=True))
    total_tweet_engagement = db.Column(db.Integer)
try:
    with app.app_context():
        # Create the database tables
        db.create_all()
except Exception as e:
    print(f"Database error: {str(e)}")

def calculate_engagement(tweet):
    likes = tweet.likes
    retweets = tweet.retweets
    replies = tweet.replies
    
    # Define weights based on the importance you assign to each metric
    weights = {'likes': 1, 'retweets': 2, 'replies': 1.5}
    
    # Calculate the time decay factor based on the age of the tweet
    hours_since_tweet = (datetime.utcnow() - tweet.timestamp).total_seconds() / 3600
    decay_factor = 0.5 ** (hours_since_tweet / 3)  # Half-life of 3 hours
    
    engagement_score = (likes*weights['likes'] + retweets*weights['retweets'] + replies*weights['replies']) * decay_factor
    
    return engagement_score

def calculate_normalized_engagement(total_engagement, num_tweets, followers, time_window=24):
    # Calculate the average tweets per hour
    avg_tweets_per_hour = num_tweets / time_window
    
    # Define a weight for the time factor based on your specific needs
    time_weight = 0.5
    
    # Adjust the total engagement with the time factor
    adjusted_engagement = total_engagement * (1 + time_weight * avg_tweets_per_hour)
    
    normalized_engagement = float(adjusted_engagement / followers)
    
    return normalized_engagement

def get_current_engagement():
    # Get the datetime for 24 hours ago
    a_day_ago = datetime.utcnow() - timedelta(hours=24)

    # Define the maximum possible engagement score
    max_possible_engagement = 100000.0 

    # Get all users
    users = User.query.order_by(User.id.asc()).limit(7).all()
    if not users:
        app.logger.warning("No User records found")
        return jsonify({"error": "No User records found"})

    # Number of followers for each user --> ordered by user id (?)
    followers = [340000.0, 3300000.0, 3300000.0, 125000.0, 345000.0, 100000.0, 90000.0]

    # Initialize a list to store user engagement
    user_engagements = []

    # Calculate total engagement for all users
    for i, user in enumerate(users):
        # Get the recent tweets for the user
        recent_tweets = Tweet.query.filter(Tweet.user_id == user.id, Tweet.timestamp >= a_day_ago).all()
        
        # Calculate total engagement and max engagement for each tweet
        engagements = [calculate_engagement(tweet) for tweet in recent_tweets]
        total_engagement = sum(engagements)
        max_engagement = max(engagements) if engagements else 0
        
        # Normalize the engagement value according to the number of followers and number of recent tweets
        if not recent_tweets:
            normalized_engagement = 0.0
        else:
            normalized_engagement = calculate_normalized_engagement(total_engagement, max_engagement, len(recent_tweets), followers[i]) / max_possible_engagement
        
        # Add the user and their normalized engagement to the list
        user_engagements.append((user.name, normalized_engagement))

    # Sort the list by engagement in descending order
    user_engagements.sort(key=lambda x: x[1], reverse=True)

    # Return the sorted list of tuples
    return user_engagements


@app.route('/engagement', methods=['GET'])
def engagement_route():
    return get_current_engagement()

@app.route('/')
def index():
    # Get current engagement
    user_engagements = get_current_engagement()

    # Fetch the latest TotalIncrease
    last_total_increase = TotalIncrease.query.order_by(TotalIncrease.timestamp.desc()).first()
    
    # Get total increases in the last 6 hours
    six_hours_ago = datetime.now() - timedelta(hours=6)
    total_increases = TotalIncrease.query.filter(TotalIncrease.timestamp >= six_hours_ago).order_by(TotalIncrease.timestamp.desc()).all()

    # Calculate the average engagement over the past 6 hours
    average_engagement = sum([increase.total_tweet_engagement for increase in total_increases]) / len(total_increases) if total_increases else 0

    # Check for peak occurrences
    peak_occurrences = []
    for increase in total_increases:
        if increase.total_tweet_engagement > average_engagement * 1.1:  # 1.5 is an example threshold for "significant" increase
            peak_occurrences.append((increase.timestamp, increase.total_tweet_engagement))

    # Determine if the total tweet engagement is below average, average, or above average
    latest_engagement = total_increases[0].total_tweet_engagement if total_increases else 0
    if latest_engagement < 500000:
        engagement_level = "NO"
    elif latest_engagement < 600000:
        engagement_level = "?"
    else:
        engagement_level = "SÍ"
    
    # Get the tweet with hate speech content
    hate_tweet = Tweet.query.filter(Tweet.content.isnot(None)).order_by(Tweet.id.desc()).first()

    # Check if a hate tweet was found
    if hate_tweet is not None:
        hate_tweet_content = hate_tweet.content
    else:
        hate_tweet_content = None

    return render_template('index.html', timedelta=timedelta, hate_tweet_content=hate_tweet_content, datetime=datetime, pytz=pytz, user_engagements=user_engagements, peak_occurrences=peak_occurrences, engagement_level=engagement_level, last_total_increase=last_total_increase, min=min)







