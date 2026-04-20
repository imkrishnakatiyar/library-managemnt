from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'library_secret_key_2024'

DB_PATH = 'library.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        isbn TEXT UNIQUE NOT NULL,
        genre TEXT,
        year INTEGER,
        total_copies INTEGER DEFAULT 1,
        available_copies INTEGER DEFAULT 1,
        description TEXT,
        added_on TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        member_id TEXT UNIQUE NOT NULL,
        joined_on TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER NOT NULL,
        member_id INTEGER NOT NULL,
        issued_on TEXT DEFAULT CURRENT_TIMESTAMP,
        due_date TEXT NOT NULL,
        returned_on TEXT,
        status TEXT DEFAULT 'issued',
        FOREIGN KEY(book_id) REFERENCES books(id),
        FOREIGN KEY(member_id) REFERENCES members(id)
    )''')

    # Seed sample data
    c.execute("SELECT COUNT(*) FROM books")
    if c.fetchone()[0] == 0:
        sample_books = [
            ('The Great Gatsby', 'F. Scott Fitzgerald', '978-0743273565', 'Fiction', 1925, 3, 3, 'A story of the Jazz Age'),
            ('To Kill a Mockingbird', 'Harper Lee', '978-0061935466', 'Fiction', 1960, 2, 2, 'A classic of American literature'),
            ('1984', 'George Orwell', '978-0451524935', 'Dystopian', 1949, 4, 4, 'A dystopian social science fiction'),
            ('The Alchemist', 'Paulo Coelho', '978-0062315007', 'Fiction', 1988, 3, 3, 'A philosophical novel'),
            ('Sapiens', 'Yuval Noah Harari', '978-0062316097', 'Non-Fiction', 2011, 2, 2, 'A brief history of humankind'),
            ('Atomic Habits', 'James Clear', '978-0735211292', 'Self-Help', 2018, 5, 5, 'Build good habits, break bad ones'),
            ('The Pragmatic Programmer', 'David Thomas', '978-0135957059', 'Technology', 1999, 2, 2, 'A guide to software craftsmanship'),
            ('Dune', 'Frank Herbert', '978-0441013593', 'Sci-Fi', 1965, 3, 3, 'Epic science fiction saga'),
        ]
        c.executemany('INSERT INTO books (title, author, isbn, genre, year, total_copies, available_copies, description) VALUES (?,?,?,?,?,?,?,?)', sample_books)

        sample_members = [
            ('Alice Johnson', 'alice@email.com', '9876543210', 'LIB001'),
            ('Bob Smith', 'bob@email.com', '9876543211', 'LIB002'),
            ('Carol White', 'carol@email.com', '9876543212', 'LIB003'),
        ]
        c.executemany('INSERT INTO members (name, email, phone, member_id) VALUES (?,?,?,?)', sample_members)

    conn.commit()
    conn.close()

@app.route('/')
def index():
    conn = get_db()
    stats = {
        'total_books': conn.execute("SELECT COUNT(*) FROM books").fetchone()[0],
        'total_members': conn.execute("SELECT COUNT(*) FROM members").fetchone()[0],
        'active_issues': conn.execute("SELECT COUNT(*) FROM transactions WHERE status='issued'").fetchone()[0],
        'available_books': conn.execute("SELECT SUM(available_copies) FROM books").fetchone()[0] or 0,
    }
    recent_transactions = conn.execute("""
        SELECT t.id, b.title, m.name, m.member_id, t.issued_on, t.due_date, t.status
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        JOIN members m ON t.member_id = m.id
        ORDER BY t.issued_on DESC LIMIT 5
    """).fetchall()
    conn.close()
    return render_template('index.html', stats=stats, recent=recent_transactions)

@app.route('/catalogue')
def catalogue():
    query = request.args.get('q', '')
    genre = request.args.get('genre', '')
    conn = get_db()

    sql = "SELECT * FROM books WHERE 1=1"
    params = []
    if query:
        sql += " AND (title LIKE ? OR author LIKE ? OR isbn LIKE ?)"
        params += [f'%{query}%', f'%{query}%', f'%{query}%']
    if genre:
        sql += " AND genre = ?"
        params.append(genre)
    sql += " ORDER BY title"

    books = conn.execute(sql, params).fetchall()
    genres = conn.execute("SELECT DISTINCT genre FROM books ORDER BY genre").fetchall()
    conn.close()
    return render_template('catalogue.html', books=books, genres=genres, query=query, selected_genre=genre)

@app.route('/books/add', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        conn = get_db()
        try:
            conn.execute("""INSERT INTO books (title, author, isbn, genre, year, total_copies, available_copies, description)
                VALUES (?,?,?,?,?,?,?,?)""",
                (request.form['title'], request.form['author'], request.form['isbn'],
                 request.form['genre'], request.form['year'], request.form['copies'],
                 request.form['copies'], request.form['description']))
            conn.commit()
            flash('Book added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('ISBN already exists!', 'error')
        finally:
            conn.close()
        return redirect(url_for('catalogue'))
    return render_template('add_book.html')

@app.route('/books/edit/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    conn = get_db()
    book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    if request.method == 'POST':
        conn.execute("""UPDATE books SET title=?, author=?, isbn=?, genre=?, year=?,
            total_copies=?, description=? WHERE id=?""",
            (request.form['title'], request.form['author'], request.form['isbn'],
             request.form['genre'], request.form['year'], request.form['copies'],
             request.form['description'], book_id))
        conn.commit()
        conn.close()
        flash('Book updated successfully!', 'success')
        return redirect(url_for('catalogue'))
    conn.close()
    return render_template('edit_book.html', book=book)

@app.route('/books/delete/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    conn = get_db()
    conn.execute("DELETE FROM books WHERE id=?", (book_id,))
    conn.commit()
    conn.close()
    flash('Book deleted!', 'success')
    return redirect(url_for('catalogue'))

@app.route('/members')
def members():
    conn = get_db()
    members = conn.execute("""
        SELECT m.*, COUNT(CASE WHEN t.status='issued' THEN 1 END) as active_books
        FROM members m
        LEFT JOIN transactions t ON m.id = t.member_id
        GROUP BY m.id ORDER BY m.name
    """).fetchall()
    conn.close()
    return render_template('members.html', members=members)

@app.route('/members/add', methods=['GET', 'POST'])
def add_member():
    if request.method == 'POST':
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        member_id = f"LIB{count+1:03d}"
        try:
            conn.execute("INSERT INTO members (name, email, phone, member_id) VALUES (?,?,?,?)",
                (request.form['name'], request.form['email'], request.form['phone'], member_id))
            conn.commit()
            flash(f'Member added! ID: {member_id}', 'success')
        except sqlite3.IntegrityError:
            flash('Email already registered!', 'error')
        finally:
            conn.close()
        return redirect(url_for('members'))
    return render_template('add_member.html')

@app.route('/desk', methods=['GET', 'POST'])
def desk():
    conn = get_db()
    books = conn.execute("SELECT id, title, author, available_copies FROM books WHERE available_copies > 0 ORDER BY title").fetchall()
    members = conn.execute("SELECT id, name, member_id FROM members ORDER BY name").fetchall()
    active_issues = conn.execute("""
        SELECT t.id, b.title, b.id as book_id, m.name, m.member_id, t.issued_on, t.due_date,
               CASE WHEN date(t.due_date) < date('now') THEN 1 ELSE 0 END as overdue
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        JOIN members m ON t.member_id = m.id
        WHERE t.status = 'issued'
        ORDER BY t.due_date ASC
    """).fetchall()
    conn.close()
    return render_template('desk.html', books=books, members=members, active_issues=active_issues)

@app.route('/issue', methods=['POST'])
def issue_book():
    conn = get_db()
    book_id = request.form['book_id']
    member_id = request.form['member_id']
    days = int(request.form.get('days', 14))
    due = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

    book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    if book['available_copies'] < 1:
        flash('No copies available!', 'error')
        conn.close()
        return redirect(url_for('desk'))

    conn.execute("INSERT INTO transactions (book_id, member_id, due_date) VALUES (?,?,?)", (book_id, member_id, due))
    conn.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id=?", (book_id,))
    conn.commit()
    conn.close()
    flash('Book issued successfully!', 'success')
    return redirect(url_for('desk'))

@app.route('/return/<int:transaction_id>', methods=['POST'])
def return_book(transaction_id):
    conn = get_db()
    txn = conn.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,)).fetchone()
    if txn and txn['status'] == 'issued':
        conn.execute("UPDATE transactions SET status='returned', returned_on=datetime('now') WHERE id=?", (transaction_id,))
        conn.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id=?", (txn['book_id'],))
        conn.commit()
        flash('Book returned successfully!', 'success')
    conn.close()
    return redirect(url_for('desk'))

@app.route('/history')
def history():
    conn = get_db()
    transactions = conn.execute("""
        SELECT t.id, b.title, m.name, m.member_id, t.issued_on, t.due_date, t.returned_on, t.status,
               CASE WHEN t.status='issued' AND date(t.due_date) < date('now') THEN 1 ELSE 0 END as overdue
        FROM transactions t
        JOIN books b ON t.book_id = b.id
        JOIN members m ON t.member_id = m.id
        ORDER BY t.issued_on DESC
    """).fetchall()
    conn.close()
    return render_template('history.html', transactions=transactions)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
