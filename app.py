from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from flask_bcrypt import Bcrypt
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key'
bcrypt = Bcrypt(app)

# Database connection function with table creation
def connect_db():
    conn = sqlite3.connect('users.db')  # Replace with your database filename
    cursor = conn.cursor()

    # Create table if it doesn't exist
    create_table_sql = """CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    );"""
    cursor.execute(create_table_sql)
    conn.commit()

    return conn
def get_recommendations(user_ratings):
    conn = sqlite3.connect('users.db')
    query = "select movieId,title,genres from movies"
    movies  = pd.read_sql_query(query, conn)
    genres_combined = movies['genres'].str.replace('|', ' ')
    tfidf = TfidfVectorizer()
    tfidf_matrix = tfidf.fit_transform(genres_combined)
# Calculate the cosine similarity matrix between the movies
    cosine_similarity_matrix = cosine_similarity(tfidf_matrix)
# Create a dataframe with the cosine similarity scores
    similarity_df = pd.DataFrame(cosine_similarity_matrix, index=movies['title'], columns=movies['title'])
    cumulative_similarity = [0] * len(movies)
    for user_rating in user_ratings:
        movie = user_rating['title']
        rating = user_rating['rating']
        movie_index = similarity_df.index.get_loc(movie)
        cumulative_similarity += similarity_df.iloc[movie_index] * rating
    normalized_similarity = cumulative_similarity / sum(user_rating['rating'] for user_rating in user_ratings)
    top=normalized_similarity.sort_values(ascending=False)[1:21]
    print(top)
    recommended_movies=[]
    for movie in top.index.tolist():
        recommended_movies+=[[movie,movies.loc[movies['title'] == movie, 'genres'].values[0]]]
    return recommended_movies

    
def get_random_movies():
    conn = sqlite3.connect('users.db')  # Replace with your database filename
    cursor = conn.cursor()
    cursor.execute("SELECT movieId, title, genres FROM movies ORDER BY RANDOM() LIMIT 5")
    random_movies = cursor.fetchall()
    conn.close()
    return random_movies
# User validation function
def is_user_valid(username, password):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? ", (username,))
    user = cursor.fetchone()
    if user is None:
        return None
    conn.close()
    if bcrypt.check_password_hash(user[1], password) :
        return user is not None
    return None
# User registration function (with password hashing)
def register_user(username, password):
     # Install passlib for password hashing
      # Hash the password securely
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
    conn.commit()
    conn.close()

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if is_user_valid(username, password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            error = 'Invalid username or password'
            return render_template('login.html', error=error)
    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

# Index route (protected)
@app.route('/')
def index():
    if 'username' in session:
        username = session['username']
        random_movies=get_random_movies()
        return render_template('index.html', username=username,movies=random_movies,recommended_movies=None)
    else:
        return redirect(url_for('login'))
@app.route('/submit_ratings', methods=['POST'])
def submit_ratings():
    random_movies=get_random_movies()
    if 'username' in session:
        username = session['username']
    else:
        return redirect(url_for('login'))
    form_data = request.form
    user_ratings=[]
    for title,rating in form_data.items():
        user_ratings.append({'title': title, 'rating': int(rating)})
    # Process user ratings (you can store them in a database or perform other actions)
    recommended_movies=get_recommendations(user_ratings)
    return render_template('recommendations.html', username=username,recommended_movies=recommended_movies)
# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Check for existing username
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = cursor.fetchone()
        conn.close()
        if existing_user:
            error = 'Username already exists!'
            return render_template('register.html', error=error)
        else:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            register_user(username,  hashed_password)
            return redirect(url_for('login'))  # Redirect to login after registration
    return render_template('register.html')

if __name__ == '__main__':
    connect_db()  # Ensure database and table exist
    app.run(debug=True)
